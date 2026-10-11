(function () {
  'use strict';

  document.documentElement.classList.add('basera-admin');

  function ensureRtl() {
    var lang = (document.documentElement.lang || '').toLowerCase();
    if (lang.indexOf('ar') === 0 || document.body.classList.contains('rtl')) {
      document.documentElement.setAttribute('dir', 'rtl');
    }
  }

  function enhanceSelects(root) {
    var scope = root || document;
    var selects = scope.querySelectorAll('select');
    selects.forEach(function (el) {
      if (el.dataset.baseraSelectReady === '1') return;
      el.dataset.baseraSelectReady = '1';
      el.classList.add('basera-select');
      // ضمان ظهور القيمة الحالية بوضوح عند التركيز
      el.addEventListener('focus', function () {
        el.style.outline = 'none';
      });
    });
  }

  function enhanceNavFilter() {
    var navFilter = document.getElementById('nav-filter');
    if (navFilter && !navFilter.getAttribute('placeholder')) {
      navFilter.setAttribute('placeholder', 'بحث في القوائم…');
    }
  }

  function applyQuestionType(select) {
    var box = select.closest('.inline-related') || select.closest('form') || document;
    var type = select.value;
    box.querySelectorAll('.basera-tf-fields').forEach(function (el) {
      el.style.display = type === 'true_false' ? '' : 'none';
    });
    box.querySelectorAll('.basera-mcq-fields').forEach(function (el) {
      el.style.display = type === 'multiple_choice' ? '' : 'none';
    });
  }

  function toggleQuestionChoiceFields(root) {
    var scope = root || document;
    var selects = scope.querySelectorAll(
      'select[name$="-question_type"], select[name="question_type"], select[id$="-question_type"], select[id="id_question_type"]'
    );
    selects.forEach(function (select) {
      applyQuestionType(select);
      if (select.dataset.baseraTypeBound === '1') return;
      select.dataset.baseraTypeBound = '1';
      select.addEventListener('change', function () {
        applyQuestionType(select);
      });
    });
  }

  function boot() {
    ensureRtl();
    enhanceNavFilter();
    enhanceSelects(document);
    toggleQuestionChoiceFields(document);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

  // بعد تهيئة autocomplete/select2 في Django
  document.addEventListener('formset:added', function (e) {
    enhanceSelects(e.target || document);
    toggleQuestionChoiceFields(e.target || document);
  });

  // راقب العناصر المضافة ديناميكياً (Select2)
  if (window.MutationObserver) {
    var observer = new MutationObserver(function (mutations) {
      mutations.forEach(function (m) {
        m.addedNodes.forEach(function (node) {
          if (node.nodeType === 1) enhanceSelects(node);
        });
      });
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }
})();
