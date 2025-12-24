(() => {
  const printButton = document.querySelector('[data-action="print"]');
  if (printButton) {
    printButton.addEventListener("click", () => {
      window.print();
    });
  }
})();
