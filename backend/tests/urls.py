from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import QuizViewSet, QuizAttemptViewSet

router = DefaultRouter()
# تسجيل المسار الأدق أولاً حتى لا يُفسَّر "attempts" كمعرّف اختبار
router.register(r'attempts', QuizAttemptViewSet, basename='quiz-attempt')
router.register(r'', QuizViewSet, basename='quiz')

urlpatterns = [
    path('', include(router.urls)),
]
