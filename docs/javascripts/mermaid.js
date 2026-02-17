/* global mermaid, document$ */

(function () {
  function initMermaid() {
    if (typeof mermaid === "undefined") {
      return;
    }

    mermaid.initialize({
      startOnLoad: false
    });

    var nodes = document.querySelectorAll(".mermaid");
    if (nodes.length > 0) {
      mermaid.init(undefined, nodes);
    }
  }

  if (typeof document$ !== "undefined" && document$ !== null) {
    document$.subscribe(function () {
      initMermaid();
    });
  } else {
    document.addEventListener("DOMContentLoaded", function () {
      initMermaid();
    });
  }
})();
