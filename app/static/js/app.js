// Small progressive enhancements. Every page still works with JavaScript off.
document.addEventListener("DOMContentLoaded", function () {
  // Show the current value next to each slider.
  document.querySelectorAll("input[type=range][data-output]").forEach(function (input) {
    var out = document.getElementById(input.dataset.output);
    var update = function () { out.textContent = input.value; };
    input.addEventListener("input", update);
    update();
  });

  // Ask before destructive actions, e.g. <form data-confirm="Deactivate this user?">
  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      if (!window.confirm(form.dataset.confirm)) e.preventDefault();
    });
  });

  // Print buttons.
  document.querySelectorAll("[data-print]").forEach(function (btn) {
    btn.addEventListener("click", function () { window.print(); });
  });

  // Stop double submission (e.g. saving the same assessment twice).
  document.querySelectorAll("form[data-once]").forEach(function (form) {
    form.addEventListener("submit", function () {
      var btn = form.querySelector("button[type=submit]");
      if (btn) { btn.disabled = true; btn.textContent = "Please wait..."; }
    });
  });
});
