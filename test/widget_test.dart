import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:basera/main.dart';
import 'package:basera/models/quiz.dart';
import 'package:basera/models/user.dart';
import 'package:basera/models/grade.dart';
import 'package:basera/models/lesson.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUpAll(() {
    GoogleFonts.config.allowRuntimeFetching = false;
  });

  group('محولات JSON', () {
    test('Quiz.fromJson يتحمل lesson كنص ولا يعتمد على is_correct', () {
      final quiz = Quiz.fromJson({
        'id': 7,
        'lesson': '12',
        'lesson_title': 'درس منشور',
        'title': 'اختبار الرياضيات',
        'description': 'وصف',
        'passing_score': 70,
        'questions_count': 2,
        'created_at': '2026-09-17T10:00:00.000Z',
        'questions': [
          {
            'id': 1,
            'question_type': 'multiple_choice',
            'question_text': 'كم يساوي 2+2؟',
            'order': 1,
            'points': 1,
            'choices': [
              {'id': 10, 'choice_text': '4'},
              {'id': 11, 'choice_text': '5'},
            ],
          },
        ],
      });

      expect(quiz.id, 7);
      expect(quiz.lessonId, 12);
      expect(quiz.title, 'اختبار الرياضيات');
      expect(quiz.questions, isNotNull);
      expect(quiz.questions!.first.choices, hasLength(2));
      expect(quiz.questions!.first.choices.every((c) => c.isCorrect == false), isTrue);
    });

    test('User.fromJson يقرأ حقول التسجيل', () {
      final user = User.fromJson({
        'id': 3,
        'username': 'student1',
        'email': 's@example.com',
        'first_name': 'أحمد',
        'last_name': 'علي',
        'user_type': 'student',
        'phone_number': '0590000000',
        'date_joined': '2026-09-01T08:00:00.000Z',
      });
      expect(user.username, 'student1');
      expect(user.userType, 'student');
      expect(user.firstName, 'أحمد');
    });

    test('Grade.fromJson و Lesson.fromJson يقرآن استجابة الـ API', () {
      final grade = Grade.fromJson({
        'id': 1,
        'name': 'الصف التاسع',
        'subjects_count': 2,
        'order': 9,
        'is_active': true,
      });
      expect(grade.subjectsCount, 2);

      final lesson = Lesson.fromJson({
        'id': 4,
        'title': 'درس منشور',
        'category': 2,
        'category_name': 'الرياضيات',
        'transcribed_text_reviewed': false,
        'duration': 0,
        'status': 'published',
        'sections': [],
        'conversion_progress': 100,
      });
      expect(lesson.categoryId, 2);
      expect(lesson.status, 'published');
    });
  });

  testWidgets('شاشة الدخول تظهر للطالب غير المسجّل', (tester) async {
    SharedPreferences.setMockInitialValues({});

    await tester.pumpWidget(const BaseraApp());
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.text('بصيرة'), findsWidgets);
    expect(find.text('تسجيل الدخول'), findsOneWidget);
    expect(find.text('دخول'), findsOneWidget);
    expect(find.byType(TextFormField), findsNWidgets(2));

    expect(
      tester
          .widgetList<Directionality>(find.byType(Directionality))
          .any((d) => d.textDirection == TextDirection.rtl),
      isTrue,
    );
  });

  testWidgets('التحقق من الحقول الفارغة قبل الدخول', (tester) async {
    SharedPreferences.setMockInitialValues({});

    await tester.pumpWidget(const BaseraApp());
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    await tester.tap(find.text('دخول'));
    await tester.pump();

    expect(find.text('الرجاء إدخال اسم المستخدم'), findsOneWidget);
    expect(find.text('الرجاء إدخال كلمة المرور'), findsOneWidget);
  });
}
