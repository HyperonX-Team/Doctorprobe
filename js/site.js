// Doctordrobe Docs - sidebar search filter, mobile toggle, copy buttons.

(function () {
  "use strict";

  // Highlight the current page in the sidebar.
  var current = (window.location.pathname.split("/").pop() || "index.html").toLowerCase();
  document.querySelectorAll(".sidebar a[href]").forEach(function (link) {
    var href = link.getAttribute("href").toLowerCase();
    if (href === current || (current === "" && href === "index.html")) {
      link.classList.add("active");
    }
  });

  // Mobile sidebar toggle.
  var menuBtn = document.getElementById("menu-btn");
  var sidebar = document.getElementById("sidebar");
  if (menuBtn && sidebar) {
    menuBtn.addEventListener("click", function () {
      sidebar.classList.toggle("open");
    });
    document.addEventListener("click", function (event) {
      if (
        sidebar.classList.contains("open") &&
        !sidebar.contains(event.target) &&
        event.target !== menuBtn
      ) {
        sidebar.classList.remove("open");
      }
    });
  }

  // Sidebar search filter.
  var search = document.getElementById("docs-search");
  var noResults = document.getElementById("no-results");
  if (search && noResults) {
    search.addEventListener("input", function () {
      var query = search.value.trim().toLowerCase();
      var visible = 0;
      document.querySelectorAll(".sidebar a[href]").forEach(function (link) {
        var haystack = (link.textContent + " " + link.getAttribute("data-keywords") || "").toLowerCase();
        var match = query === "" || haystack.indexOf(query) !== -1;
        link.setAttribute("data-hidden", match ? "false" : "true");
        if (match) visible += 1;
      });
      noResults.setAttribute("data-shown", visible === 0 ? "true" : "false");
    });
  }

  // Copy-to-clipboard on code blocks.
  document.querySelectorAll("pre").forEach(function (pre) {
    var button = document.createElement("button");
    button.type = "button";
    button.className = "copy-btn";
    button.textContent = "Copy";
    button.addEventListener("click", function () {
      var text = pre.querySelector("code") ? pre.querySelector("code").innerText : pre.innerText;
      var done = function () {
        button.textContent = "Copied!";
        setTimeout(function () {
          button.textContent = "Copy";
        }, 1500);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done).catch(done);
      } else {
        var range = document.createRange();
        range.selectNodeContents(pre);
        var selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
        done();
      }
    });
    pre.appendChild(button);
  });
})();
