"""Tests for Show Answer overrides for self-paced courses."""

import ddt

from django.test.utils import override_settings

from common.lib.xmodule.xmodule.capa_base import SHOWANSWER
from lms.djangoapps.ccx.tests.test_overrides import inject_field_overrides
from openedx.features.course_experience import RELATIVE_DATES_FLAG
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory, ItemFactory


@override_settings(
    FIELD_OVERRIDE_PROVIDERS=[
        'lms.djangoapps.show_answer.show_answer_field_override.ShowAnswerFieldOverride'
    ],
)
@ddt.ddt
class ShowAnswerFieldOverrideTest(ModuleStoreTestCase):
    """ Tests for Show Answer overrides for self-paced courses. """

    def setup_course(self, **course_kwargs):
        """ Set up a course with provided course attributes. """
        course = CourseFactory.create(**course_kwargs)
        inject_field_overrides((course,), course, self.user)
        return course

    @ddt.data(True, False)
    def test_override_enabled_for(self, active):
        with RELATIVE_DATES_FLAG.override(active=active):
            # Instructor paced course will just have the default value
            ip_course = self.setup_course()
            self.assertEqual(ip_course.showanswer, SHOWANSWER.FINISHED)
            sp_course = self.setup_course(self_paced=True)
            if active:
                self.assertEqual(sp_course.showanswer, SHOWANSWER.AFTER_ALL_ATTEMPTS_OR_CORRECT)
            else:
                self.assertEqual(sp_course.showanswer, SHOWANSWER.FINISHED)

    @ddt.data(
        (SHOWANSWER.ATTEMPTED, SHOWANSWER.ATTEMPTED_NO_PAST_DUE),
        (SHOWANSWER.CLOSED, SHOWANSWER.AFTER_ALL_ATTEMPTS),
        (SHOWANSWER.CORRECT_OR_PAST_DUE, SHOWANSWER.ANSWERED),
        (SHOWANSWER.FINISHED, SHOWANSWER.AFTER_ALL_ATTEMPTS_OR_CORRECT),
        (SHOWANSWER.PAST_DUE, SHOWANSWER.NEVER),
        (SHOWANSWER.NEVER, SHOWANSWER.NEVER),
        (SHOWANSWER.AFTER_SOME_NUMBER_OF_ATTEMPTS, SHOWANSWER.AFTER_SOME_NUMBER_OF_ATTEMPTS),
        (SHOWANSWER.ALWAYS, SHOWANSWER.ALWAYS),
    )
    @ddt.unpack
    @RELATIVE_DATES_FLAG.override(active=True)
    def test_get(self, initial_value, expected_final_value):
        course = self.setup_course(self_paced=True, showanswer=initial_value)
        del course._field_data_cache['showanswer']
        self.assertEqual(course.showanswer, expected_final_value)
