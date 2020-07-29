"""
Outline Tab Views
"""

from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.exceptions import APIException, ParseError
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django.utils.translation import ugettext as _
from edx_django_utils import monitoring as monitoring_utils
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from django.http.response import Http404
from django.urls import reverse
from django.utils.translation import ugettext as _
from opaque_keys.edx.keys import CourseKey

from course_modes.models import CourseMode
from lms.djangoapps.course_api.blocks.transformers.blocks_api import BlocksAPITransformer
from lms.djangoapps.course_blocks.api import get_course_block_access_transformers, get_course_blocks
from lms.djangoapps.course_home_api.outline.v1.serializers import OutlineTabSerializer
from lms.djangoapps.course_home_api.toggles import course_home_mfe_dates_tab_is_active, course_home_mfe_outline_tab_is_active
from lms.djangoapps.course_home_api.utils import get_microfrontend_url
from lms.djangoapps.courseware.access import has_access
from lms.djangoapps.courseware.context_processor import user_timezone_locale_prefs
from lms.djangoapps.courseware.courses import get_course_date_blocks, get_course_info_section, get_course_with_access
from lms.djangoapps.courseware.date_summary import TodaysDate
from lms.djangoapps.courseware.masquerade import setup_masquerade
from openedx.core.djangoapps.content.block_structure.transformers import BlockStructureTransformers
from openedx.core.djangoapps.user_api.course_tag.api import get_course_tag, set_course_tag
from openedx.features.course_experience import COURSE_ENABLE_UNENROLLED_ACCESS_FLAG, LATEST_UPDATE_FLAG
from openedx.features.course_experience.course_tools import CourseToolsPluginManager
from openedx.features.course_experience.utils import get_course_outline_block_tree, get_resume_block
from openedx.features.course_experience.views.latest_update import LatestUpdateFragmentView
from openedx.features.course_experience.views.welcome_message import PREFERENCE_KEY, WelcomeMessageFragmentView
from student.models import CourseEnrollment
from xmodule.course_module import COURSE_VISIBILITY_PUBLIC
from xmodule.modulestore.django import modulestore


class UnableToDismissWelcomeMessage(APIException):
    status_code = 400
    default_detail = 'Unable to dismiss welcome message.'
    default_code = 'unable_to_dismiss_welcome_message'


class OutlineTabView(RetrieveAPIView):
    """
    **Use Cases**

        Request details for the Outline Tab

    **Example Requests**

        GET api/course_home/v1/outline/{course_key}

    **Response Values**

        Body consists of the following fields:

        course_blocks:
            blocks: List of serialized Course Block objects. Each serialization has the following fields:
                id: (str) The usage ID of the block.
                type: (str) The type of block. Possible values the names of any
                    XBlock type in the system, including custom blocks. Examples are
                    course, chapter, sequential, vertical, html, problem, video, and
                    discussion.
                display_name: (str) The display name of the block.
                lms_web_url: (str) The URL to the navigational container of the
                    xBlock on the web LMS.
                children: (list) If the block has child blocks, a list of IDs of
                    the child blocks.
        course_tools: List of serialized Course Tool objects. Each serialization has the following fields:
            analytics_id: (str) The unique id given to the tool.
            title: (str) The display title of the tool.
            url: (str) The link to access the tool.
        dates_widget:
            course_date_blocks: List of serialized Course Dates objects. Each serialization has the following fields:
                complete: (bool) Meant to only be used by assignments. Indicates completeness for an
                assignment.
                date: (datetime) The date time corresponding for the event
                date_type: (str) The type of date (ex. course-start-date, assignment-due-date, etc.)
                description: (str) The description for the date event
                learner_has_access: (bool) Indicates if the learner has access to the date event
                link: (str) An absolute link to content related to the date event
                    (ex. verified link or link to assignment)
                title: (str) The title of the date event
            dates_tab_link: (str) The URL to the Dates Tab
            user_timezone: (str) The timezone of the given user
        enroll_alert:
            can_enroll: (bool) Whether the user can enroll in the given course
            extra_text: (str)
        handouts_html: (str) Raw HTML for the handouts section of the course info
        resume_course:
            has_visited_course: (bool) Whether the user has ever visited the course
            url: (str) The display name of the course block to resume
        welcome_message_html: (str) Raw HTML for the course updates banner

    **Returns**

        * 200 on success with above fields.
        * 403 if the user is not authenticated.
        * 404 if the course is not available or cannot be seen.

    """

    permission_classes = (IsAuthenticated,)
    serializer_class = OutlineTabSerializer

    def get(self, request, *args, **kwargs):
        course_key_string = kwargs.get('course_key_string')
        course_key = CourseKey.from_string(course_key_string)
        course_usage_key = modulestore().make_course_usage_key(course_key)

        if not course_home_mfe_outline_tab_is_active(course_key):
            raise Http404

        # Enable NR tracing for this view based on course
        monitoring_utils.set_custom_metric('course_id', course_key_string)
        monitoring_utils.set_custom_metric('user_id', request.user.id)
        monitoring_utils.set_custom_metric('is_staff', request.user.is_staff)

        course = get_course_with_access(request.user, 'load', course_key, check_if_enrolled=False)

        _masquerade, request.user = setup_masquerade(
            request,
            course_key,
            staff_access=has_access(request.user, 'staff', course_key),
            reset_masquerade_data=True,
        )

        enrollment = CourseEnrollment.get_enrollment(request.user, course_key)
        allow_anonymous = COURSE_ENABLE_UNENROLLED_ACCESS_FLAG.is_enabled(course_key)
        allow_public = allow_anonymous and course.course_visibility == COURSE_VISIBILITY_PUBLIC
        is_enrolled = enrollment and enrollment.is_active
        is_staff = has_access(request.user, 'staff', course_key)
        show_enrolled = is_enrolled or is_staff

        show_handouts = show_enrolled or allow_public
        handouts_html = get_course_info_section(request, request.user, course, 'handouts') if show_handouts else ''

        welcome_message_html = None
        if get_course_tag(request.user, course_key, PREFERENCE_KEY) != 'False':
            if LATEST_UPDATE_FLAG.is_enabled(course_key):
                welcome_message_html = LatestUpdateFragmentView().latest_update_html(request, course)
            else:
                welcome_message_html = WelcomeMessageFragmentView().welcome_message_html(request, course)

        enroll_alert = {
            'can_enroll': True,
            'extra_text': None,
        }
        if not show_enrolled:
            if CourseMode.is_masters_only(course_key):
                enroll_alert['can_enroll'] = False
                enroll_alert['extra_text'] = _('Please contact your degree administrator or '
                                               'edX Support if you have questions.')
            elif course.invitation_only:
                enroll_alert['can_enroll'] = False

        course_tools = CourseToolsPluginManager.get_enabled_course_tools(request, course_key)
        date_blocks = get_course_date_blocks(course, request.user, request, num_assignments=1)

        # User locale settings
        user_timezone_locale = user_timezone_locale_prefs(request)
        user_timezone = user_timezone_locale['user_timezone']

        dates_tab_link = request.build_absolute_uri(reverse('dates', args=[course.id]))
        if course_home_mfe_dates_tab_is_active(course.id):
            dates_tab_link = get_microfrontend_url(course_key=course.id, view_name='dates')

        transformers = BlockStructureTransformers()
        transformers += get_course_block_access_transformers(request.user)
        transformers += [
            BlocksAPITransformer(None, None, depth=4),
        ]

        course_blocks = get_course_blocks(request.user, course_usage_key, transformers, include_completion=True)

        has_visited_course = False
        resume_course_url = None
        for block_key in course_blocks:
            if course_blocks.get_xblock_field(block_key, 'category') == 'course':
                if course_blocks.get_xblock_field(block_key, 'resume_block', False):
                    has_visited_course = True
                    resume_block_id = self._get_resume_block(course_blocks, block_key)
                else:
                    resume_block_id = self._get_start_block(course_blocks, block_key)
                path = reverse('jump_to', kwargs={
                    'course_id': course_key_string,
                    'location': str(resume_block_id)
                })
                resume_course_url = request.build_absolute_uri(path)
                break

        resume_course = {
            'has_visited_course': has_visited_course,
            'url': resume_course_url,
        }

        dates_widget = {
            'course_date_blocks': [block for block in date_blocks if not isinstance(block, TodaysDate)],
            'dates_tab_link': dates_tab_link,
            'user_timezone': user_timezone,
        }

        data = {
            'course_blocks': course_blocks,
            'course_tools': course_tools,
            'dates_widget': dates_widget,
            'enroll_alert': enroll_alert,
            'handouts_html': handouts_html,
            'resume_course': resume_course,
            'welcome_message_html': welcome_message_html,
        }
        context = self.get_serializer_context()
        context['course_key'] = course_key
        serializer = self.get_serializer_class()(data, context=context)

        return Response(serializer.data)

    def _get_start_block(self, blocks, block):
        if not blocks.get_children(block):
            return block

        children = blocks.get_children(block)
        start_block = self._get_start_block(blocks, children[0])
        return start_block

    def _get_resume_block(self, blocks, block):
        if not blocks.get_children(block):
            return block

        children = blocks.get_children(block)
        for child in children:
            is_resume_block = blocks.get_xblock_field(child, 'resume_block', False)
            if is_resume_block:
                resume_block = self._get_resume_block(blocks, child)
        return resume_block


@api_view(['POST'])
@authentication_classes((JwtAuthentication,))
@permission_classes((IsAuthenticated,))
def dismiss_welcome_message(request):
    course_id = request.data.get('course_id', None)

    # If body doesnt contain 'course_id', return 400 to client.
    if not course_id:
        raise ParseError(_("'course_id' is required."))

    # If body contains params other than 'course_id', return 400 to client.
    if len(request.data) > 1:
        raise ParseError(_("Only 'course_id' is expected."))

    try:
        course_key = CourseKey.from_string(course_id)
        set_course_tag(request.user, course_key, PREFERENCE_KEY, 'False')
        return Response({'message': _('Welcome message successfully dismissed.')})
    except Exception:
        raise UnableToDismissWelcomeMessage
