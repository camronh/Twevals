(function () {
  const saved = localStorage.getItem('ezvals:theme');
  if (saved === 'light') document.documentElement.classList.remove('dark');
})();
