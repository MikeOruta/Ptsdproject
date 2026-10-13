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

  // Show/hide button on every password field, so users can check what they typed.
  // Switching type between "password" and "text" only changes what is displayed;
  // the value sent to the server is the same.
  document.querySelectorAll("input[type=password]").forEach(function (input) {
    var wrap = document.createElement("div");
    wrap.className = "password-wrap";
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);

    var btn = document.createElement("button");
    btn.type = "button";   // not "submit", so clicking it never sends the form
    btn.className = "password-toggle";
    btn.textContent = "Show";
    btn.setAttribute("aria-label", "Show password");
    wrap.appendChild(btn);

    btn.addEventListener("click", function () {
      var hidden = input.type === "password";
      input.type = hidden ? "text" : "password";
      btn.textContent = hidden ? "Hide" : "Show";
      btn.setAttribute("aria-label", hidden ? "Hide password" : "Show password");
      input.focus();
    });
  });

  // Stop double submission (e.g. saving the same assessment twice).
  document.querySelectorAll("form[data-once]").forEach(function (form) {
    form.addEventListener("submit", function () {
      var btn = form.querySelector("button[type=submit]");
      if (btn) { btn.disabled = true; btn.textContent = "Please wait..."; }
    });
  });
});
