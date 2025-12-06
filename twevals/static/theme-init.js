(function () {
  const saved = localStorage.getItem('twevals:theme');
  if (saved === 'light') document.documentElement.classList.remove('dark');
})();
