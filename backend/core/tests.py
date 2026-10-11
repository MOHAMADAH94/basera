"""
اختبارات واجهة API لتجهيز مناقشة مشروع بصيرة.
تغطي التسجيل، الدروس المنشورة، الاختبارات، وعدم تسريب الإجابات.
"""
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework.authtoken.models import Token

from core.models import User
from lessons.models import Grade, Category, Lesson
from tests.models import Quiz, Question, Choice


@override_settings(ENABLE_SERVER_TTS=False)
class BaseraApiTests(APITestCase):
    def setUp(self):
        self.password = 'BaseraQuiz2026!'
        self.student = User.objects.create_user(
            username='student1',
            email='student1@example.com',
            password=self.password,
            user_type='student',
        )
        self.grade = Grade.objects.create(name='الصف التاسع', order=9, is_active=True)
        self.inactive_grade = Grade.objects.create(
            name='صف مخفي', order=99, is_active=False
        )
        self.math = Category.objects.create(
            grade=self.grade, name='الرياضيات', order=1, is_active=True
        )
        self.arabic = Category.objects.create(
            grade=self.grade, name='اللغة العربية', order=2, is_active=True
        )
        self.inactive_subject = Category.objects.create(
            grade=self.grade, name='مادة متوقفة', is_active=False
        )

        self.published = Lesson.objects.create(
            title='درس منشور',
            category=self.math,
            status='published',
            text_content='محتوى الدرس المنشور',
        )
        self.draft = Lesson.objects.create(
            title='درس مسودة',
            category=self.math,
            status='draft',
            text_content='لا يظهر للطالب',
        )
        self.arabic_lesson = Lesson.objects.create(
            title='درس عربي',
            category=self.arabic,
            status='published',
            text_content='نص عربي',
        )

        self.quiz = Quiz.objects.create(
            lesson=self.published,
            title='اختبار الرياضيات',
            passing_score=70,
        )
        self.hidden_quiz = Quiz.objects.create(
            lesson=self.draft,
            title='اختبار مسودة',
            passing_score=50,
        )
        self.arabic_quiz = Quiz.objects.create(
            lesson=self.arabic_lesson,
            title='اختبار عربي',
            passing_score=60,
        )

        self.mcq = Question.objects.create(
            quiz=self.quiz,
            question_type='multiple_choice',
            question_text='كم يساوي 2+2؟',
            order=1,
            points=1,
        )
        self.choice_ok = Choice.objects.create(
            question=self.mcq, choice_text='4', is_correct=True
        )
        self.choice_bad = Choice.objects.create(
            question=self.mcq, choice_text='5', is_correct=False
        )

        self.tf = Question.objects.create(
            quiz=self.quiz,
            question_type='true_false',
            question_text='الأرض كروية',
            order=2,
            points=1,
        )
        Choice.objects.create(question=self.tf, choice_text='صح', is_correct=True)
        Choice.objects.create(question=self.tf, choice_text='خطأ', is_correct=False)

    def test_api_root_ok(self):
        response = self.client.get('/api/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('status'), 'ok')
        self.assertIn('tests', response.data['endpoints'])

    def test_register_returns_token(self):
        response = self.client.post('/api/auth/register/', {
            'username': 'newstudent',
            'email': 'new@example.com',
            'password': self.password,
            'password2': self.password,
            'user_type': 'student',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('token', response.data)
        self.assertTrue(response.data['token'])
        self.assertEqual(response.data['user']['username'], 'newstudent')
        self.assertTrue(
            Token.objects.filter(key=response.data['token']).exists()
        )

    def test_login_returns_token(self):
        response = self.client.post('/api/auth/login/', {
            'username': 'student1',
            'password': self.password,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)
        self.assertEqual(response.data['user']['username'], 'student1')

    def test_login_rejects_bad_password(self):
        response = self.client.post('/api/auth/login/', {
            'username': 'student1',
            'password': 'wrong-pass',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_grades_only_active(self):
        response = self.client.get('/api/lessons/grades/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [row['name'] for row in response.data['results']]
        self.assertIn('الصف التاسع', names)
        self.assertNotIn('صف مخفي', names)

    def test_grade_subjects_excludes_inactive(self):
        url = f'/api/lessons/grades/{self.grade.id}/subjects/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [row['name'] for row in response.data]
        self.assertIn('الرياضيات', names)
        self.assertNotIn('مادة متوقفة', names)

    def test_lessons_list_hides_drafts(self):
        response = self.client.get('/api/lessons/lessons/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [row['title'] for row in response.data['results']]
        self.assertIn('درس منشور', titles)
        self.assertNotIn('درس مسودة', titles)

    def test_lessons_filter_by_category(self):
        response = self.client.get(
            f'/api/lessons/lessons/?category={self.arabic.id}'
        )
        titles = [row['title'] for row in response.data['results']]
        self.assertEqual(titles, ['درس عربي'])

    def test_quiz_list_hides_unpublished_lessons(self):
        response = self.client.get('/api/tests/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [row['title'] for row in response.data['results']]
        self.assertIn('اختبار الرياضيات', titles)
        self.assertIn('اختبار عربي', titles)
        self.assertNotIn('اختبار مسودة', titles)

    def test_quiz_filter_by_category(self):
        response = self.client.get(f'/api/tests/?category={self.arabic.id}')
        titles = [row['title'] for row in response.data['results']]
        self.assertEqual(titles, ['اختبار عربي'])
        self.assertIn('category', response.data['results'][0])

    def test_quiz_detail_does_not_leak_correct_answers(self):
        response = self.client.get(f'/api/tests/{self.quiz.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        questions = response.data['questions']
        self.assertTrue(questions)
        for question in questions:
            for choice in question.get('choices', []):
                self.assertNotIn('is_correct', choice)
                self.assertIn('choice_text', choice)

    def test_attempts_url_is_not_captured_as_quiz_pk(self):
        self.client.force_authenticate(self.student)
        response = self.client.get('/api/tests/attempts/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)

    def test_mcq_and_true_false_grading(self):
        self.client.force_authenticate(self.student)
        start = self.client.post(f'/api/tests/{self.quiz.id}/start_attempt/')
        self.assertEqual(start.status_code, status.HTTP_201_CREATED)
        attempt_id = start.data['id']

        mcq = self.client.post(
            f'/api/tests/{self.quiz.id}/submit_answer/',
            {
                'attempt_id': attempt_id,
                'question_id': self.mcq.id,
                'choice_id': self.choice_ok.id,
            },
            format='json',
        )
        self.assertEqual(mcq.status_code, status.HTTP_200_OK)
        self.assertTrue(mcq.data['is_correct'])
        self.assertEqual(mcq.data['points_earned'], 1)
        self.assertEqual(mcq.data['correct_choice_id'], self.choice_ok.id)
        self.assertEqual(mcq.data['correct_answer_text'], '4')

        tf = self.client.post(
            f'/api/tests/{self.quiz.id}/submit_answer/',
            {
                'attempt_id': attempt_id,
                'question_id': self.tf.id,
                'answer_text': 'صح',
            },
            format='json',
        )
        self.assertEqual(tf.status_code, status.HTTP_200_OK)
        self.assertTrue(tf.data['is_correct'])

        done = self.client.post(
            f'/api/tests/{self.quiz.id}/submit_attempt/',
            {'attempt_id': attempt_id},
            format='json',
        )
        self.assertEqual(done.status_code, status.HTTP_200_OK)
        self.assertEqual(done.data['score'], 100)
        self.assertTrue(done.data['passed'])

        blocked = self.client.post(
            f'/api/tests/{self.quiz.id}/submit_answer/',
            {
                'attempt_id': attempt_id,
                'question_id': self.mcq.id,
                'choice_id': self.choice_bad.id,
            },
            format='json',
        )
        self.assertEqual(blocked.status_code, status.HTTP_400_BAD_REQUEST)

    def test_true_false_wrong_answer(self):
        self.client.force_authenticate(self.student)
        start = self.client.post(f'/api/tests/{self.quiz.id}/start_attempt/')
        attempt_id = start.data['id']
        tf = self.client.post(
            f'/api/tests/{self.quiz.id}/submit_answer/',
            {
                'attempt_id': attempt_id,
                'question_id': self.tf.id,
                'answer_text': 'خطأ',
            },
            format='json',
        )
        self.assertFalse(tf.data['is_correct'])
        self.assertEqual(tf.data['points_earned'], 0)

    def test_start_attempt_requires_auth(self):
        response = self.client.post(f'/api/tests/{self.quiz.id}/start_attempt/')
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_lesson_progress_is_saved_and_kept(self):
        self.client.force_authenticate(self.student)
        start = self.client.post(
            f'/api/lessons/lessons/{self.published.id}/update_progress/',
            {'current_position': 12, 'completed': False, 'listening_time_seconds': 10},
            format='json',
        )
        self.assertEqual(start.status_code, status.HTTP_200_OK)
        self.assertFalse(start.data['completed'])

        done = self.client.post(
            f'/api/lessons/lessons/{self.published.id}/update_progress/',
            {'current_position': 40, 'completed': True, 'listening_time_seconds': 8},
            format='json',
        )
        self.assertTrue(done.data['completed'])
        self.assertGreaterEqual(done.data['listening_time_seconds'], 18)

        keep = self.client.post(
            f'/api/lessons/lessons/{self.published.id}/update_progress/',
            {'current_position': 5, 'completed': False},
            format='json',
        )
        self.assertTrue(keep.data['completed'])

        listing = self.client.get('/api/lessons/lessons/')
        published = next(
            row for row in listing.data['results'] if row['id'] == self.published.id
        )
        self.assertTrue(published['progress_completed'])
