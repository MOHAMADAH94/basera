(function () {
  'use strict';

  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var nodes = document.querySelectorAll('[data-animate]');

  if (reduceMotion || !('IntersectionObserver' in window)) {
    nodes.forEach(function (el) {
      el.classList.add('is-in');
    });
    return;
  }

  var observer = new IntersectionObserver(
    function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-in');
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.18, rootMargin: '0px 0px -8% 0px' }
  );

  nodes.forEach(function (el) {
    observer.observe(el);
  });

  // إظهار عناصر الهيرو فوراً
  document.querySelectorAll('.hero [data-animate]').forEach(function (el) {
    requestAnimationFrame(function () {
      el.classList.add('is-in');
    });
  });
})();
