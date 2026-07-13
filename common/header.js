(function () {
  var header = document.createElement('header');
  header.className = 'site-header';

  var brand = document.createElement('a');
  brand.className = 'site-brand';
  brand.href = '/';
  brand.textContent = 'home';

  var nav = document.createElement('nav');
  nav.className = 'site-nav';
  nav.setAttribute('aria-label', 'Site');

  var pages = [
    { label: 'Reading', segment: 'books' },
    { label: 'Palette', segment: 'palette' },
  ];

  var path = location.pathname;
  pages.forEach(function (p) {
    var a = document.createElement('a');
    a.className = 'site-nav-link';
    a.href = '/' + p.segment;
    a.textContent = p.label;
    if (path.indexOf('/' + p.segment) !== -1) a.classList.add('active');
    nav.appendChild(a);
  });

  header.appendChild(brand);
  header.appendChild(nav);
  document.body.insertBefore(header, document.body.firstChild);
}());
