function toggleMenu() {
  const menu = document.getElementById("mobileMenu");
  if (menu) menu.classList.toggle("show");
}

document.addEventListener("click", function (event) {
  const menu = document.getElementById("mobileMenu");
  const button = document.querySelector(".menu-button");
  if (menu && button && !menu.contains(event.target) && !button.contains(event.target)) {
    menu.classList.remove("show");
  }
});

document.addEventListener("DOMContentLoaded", function () {
  const languages = (navigator.languages || [navigator.language || ""]).join(",").toUpperCase();
  const timezone = (Intl.DateTimeFormat().resolvedOptions().timeZone || "").toUpperCase();
  const serverMarket = document.documentElement.dataset.market || "";
  const mexico = serverMarket === "mxn" || languages.includes("-MX") || timezone.includes("MEXICO");
  const market = mexico ? "mxn" : "usd";

  document.querySelectorAll(".localized-price").forEach(function (element) {
    const parts = (element.dataset[market] || "").split("|");
    const currency = element.querySelector("span");
    if (currency) currency.textContent = parts[0] || "";
    const amountNode = Array.from(element.childNodes).find(function (node) {
      return node.nodeType === Node.TEXT_NODE && node.textContent.trim();
    });
    if (amountNode) amountNode.textContent = " " + (parts[1] || "") + " ";
  });

  document.querySelectorAll(".localized-copy").forEach(function (element) {
    element.textContent = element.dataset[market] || element.textContent;
  });

  const note = document.getElementById("pricingMarketNote");
  if (note) {
    note.textContent = mexico
      ? "Precios para México en MXN."
      : "Precios internacionales de referencia en USD.";
  }
});
