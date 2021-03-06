"""
Tests for Progress Tab API in the Course Home API
"""

import ddt

from django.urls import reverse

from course_modes.models import CourseMode
from lms.djangoapps.course_home_api.tests.utils import BaseCourseHomeTests
from lms.djangoapps.course_home_api.toggles import COURSE_HOME_MICROFRONTEND
from openedx.core.djangoapps.user_api.preferences.api import set_user_preference
from openedx.core.djangoapps.waffle_utils.testutils import override_waffle_flag
from student.models import CourseEnrollment
from student.tests.factories import UserFactory


@override_waffle_flag(COURSE_HOME_MICROFRONTEND, active=True)
@ddt.ddt
class ProgressTabTestViews(BaseCourseHomeTests):
    """
    Tests for the Progress Tab API
    """
    def setUp(self):
        super().setUp()
        self.url = reverse('course-home-progress-tab', args=[self.course.id])

    @ddt.data(CourseMode.AUDIT, CourseMode.VERIFIED)
    def test_get_authenticated_enrolled_user(self, enrollment_mode):
        CourseEnrollment.enroll(self.user, self.course.id, enrollment_mode)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

        # Pulling out the courseware summary to check that the learner is able to see this info
        self.assertIsNotNone(response.data['courseware_summary'])
        for chapter in response.data['courseware_summary']:
            self.assertIsNotNone(chapter)

    def test_get_authenticated_user_not_enrolled(self):
        response = self.client.get(self.url)
        # expecting a redirect
        self.assertEqual(response.status_code, 302)

    def test_get_unauthenticated_user(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_get_unknown_course(self):
        url = reverse('course-home-progress-tab', args=['course-v1:unknown+course+2T2020'])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_masquerade(self):
        user = UserFactory()
        set_user_preference(user, 'time_zone', 'Asia/Tokyo')
        CourseEnrollment.enroll(user, self.course.id)

        self.switch_to_staff()  # needed for masquerade

        # Sanity check on our normal user
        self.assertIsNone(self.client.get(self.url).data['user_timezone'])

        # Now switch users and confirm we get a different result
        self.update_masquerade(username=user.username)
        self.assertEqual(self.client.get(self.url).data['user_timezone'], 'Asia/Tokyo')
