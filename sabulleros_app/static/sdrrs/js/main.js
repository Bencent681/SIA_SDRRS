(function () {
  "use strict";

  var toggle = document.getElementById("navToggle");
  var sidebar = document.getElementById("sidebar");
  var backdrop = document.getElementById("sidebarBackdrop");

  function closeSidebar() {
    if (sidebar) sidebar.classList.remove("open");
    if (backdrop) backdrop.classList.remove("show");
  }

  if (toggle && sidebar) {
    toggle.addEventListener("click", function () {
      sidebar.classList.toggle("open");
      if (backdrop) backdrop.classList.toggle("show", sidebar.classList.contains("open"));
    });
  }

  if (backdrop) {
    backdrop.addEventListener("click", closeSidebar);
  }

  document.querySelectorAll(".alert-close").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var alert = btn.closest(".alert");
      if (alert) alert.remove();
    });
  });

  document.querySelectorAll("[data-auto-dismiss]").forEach(function (alert) {
    setTimeout(function () {
      if (alert.parentNode) {
        alert.style.transition = "opacity .4s ease";
        alert.style.opacity = "0";
        setTimeout(function () {
          if (alert.parentNode) alert.remove();
        }, 400);
      }
    }, 5000);
  });
})();
