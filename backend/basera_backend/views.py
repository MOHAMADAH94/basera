from pathlib import Path
from django.http import Http404
from django.shortcuts import render
from django.views.static import serve as static_serve
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

NABD_ROOT = Path(__file__).resolve().parent.parent.parent / 'nabd-site'


def home(request):
    """صفحة جذر الباك اند — روابط سريعة بدل 404."""
    return render(request, 'home.html', {
        'admin_url': '/admin/',
        'api_url': '/api/',
        'front_hint': '/nabd/',
    })


def nabd_site(request, path='index.html'):
    """واجهة جمعية نبض تُخدم من الباك اند حتى لا يعتمد الموقع على منفذ 5500."""
    root = NABD_ROOT.resolve()
    if not root.is_dir():
        raise Http404('مجلد nabd-site غير موجود')
    rel = (path or 'index.html').lstrip('/')
    if not rel or rel.endswith('/'):
        rel = f'{rel}index.html'
    target = (root / rel).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise Http404() from exc
    if target.is_dir():
        target = target / 'index.html'
        rel = str(target.relative_to(root)).replace('\\', '/')
    if not target.is_file():
        raise Http404()
    return static_serve(request, rel, document_root=str(root))


@api_view(['GET'])
@permission_classes([AllowAny])
def api_root(request):
    """فهرس واجهات API."""
    base = request.build_absolute_uri('/').rstrip('/')
    return Response({
        'name': 'بصيرة API',
        'project': 'basera',
        'status': 'ok',
        'endpoints': {
            'auth': f'{base}/api/auth/',
            'login': f'{base}/api/auth/login/',
            'register': f'{base}/api/auth/register/',
            'lessons': f'{base}/api/lessons/lessons/',
            'grades': f'{base}/api/lessons/grades/',
            'categories': f'{base}/api/lessons/categories/',
            'tests': f'{base}/api/tests/',
            'volunteers': f'{base}/api/volunteers/',
            'admin': f'{base}/admin/',
            'nabd': f'{base}/nabd/',
        },
        'note': 'افتح /admin/ للوحة التحكم و /nabd/ لواجهة جمعية نبض.',
    })
