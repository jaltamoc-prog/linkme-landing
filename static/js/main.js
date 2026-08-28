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

  const motionElements = document.querySelectorAll(
    ".section-heading, .card, .step, .feature-list > div, .plan-card, details, .demo-video-panel, .demo-copy"
  );

  motionElements.forEach(function (element, index) {
    element.classList.add("motion-reveal");
    element.style.setProperty("--reveal-delay", Math.min(index % 4, 3) * 70 + "ms");
  });

  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12, rootMargin: "0px 0px -6% 0px" });

    motionElements.forEach(function (element) {
      observer.observe(element);
    });
  } else {
    motionElements.forEach(function (element) {
      element.classList.add("is-visible");
    });
  }

  const lazyMotionVideos = document.querySelectorAll(".lazy-motion-video[data-src]");
  const allStageVideos = document.querySelectorAll(".motion-stage-video");

  function prepareMotionVideo(video) {
    video.muted = true;
    video.defaultMuted = true;
    video.playsInline = true;
    video.autoplay = true;
    video.loop = true;
    video.setAttribute("muted", "");
    video.setAttribute("playsinline", "");
    video.setAttribute("webkit-playsinline", "");
    video.setAttribute("autoplay", "");
  }

  function hideManualPlay(video) {
    const stage = video.closest(".fullbleed-stage");
    const button = stage && stage.querySelector(".mobile-video-play");
    if (button) button.remove();
  }

  function showManualPlay(video) {
    const stage = video.closest(".fullbleed-stage");
    if (!stage || stage.querySelector(".mobile-video-play")) return;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "mobile-video-play";
    button.setAttribute("aria-label", "Reproducir video");
    button.innerHTML = "&#9654;";
    button.addEventListener("click", function () {
      prepareMotionVideo(video);
      const playback = video.play();
      if (playback && typeof playback.then === "function") {
        playback.then(function () { hideManualPlay(video); }).catch(function () {});
      }
    });
    stage.appendChild(button);
  }

  function playMotionVideo(video) {
    prepareMotionVideo(video);
    const playback = video.play();
    if (playback && typeof playback.then === "function") {
      playback.then(function () {
        hideManualPlay(video);
      }).catch(function () {
        showManualPlay(video);
      });
    }
  }

  function activateMotionVideo(video) {
    prepareMotionVideo(video);
    if (video.dataset.loaded !== "true") {
      video.src = video.dataset.src;
      video.dataset.loaded = "true";
      video.addEventListener("canplay", function () {
        playMotionVideo(video);
      }, { once:true });
      video.load();
    }
    playMotionVideo(video);
  }

  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    document.querySelectorAll(".motion-stage-video").forEach(function (video) {
      video.pause();
    });
    lazyMotionVideos.forEach(function (video) {
      video.removeAttribute("data-src");
    });
  } else if ("IntersectionObserver" in window) {
    const videoObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          activateMotionVideo(entry.target);
          videoObserver.unobserve(entry.target);
        }
      });
    }, { rootMargin: "300px 0px", threshold: 0.01 });

    lazyMotionVideos.forEach(function (video) {
      videoObserver.observe(video);
    });
  } else {
    lazyMotionVideos.forEach(activateMotionVideo);
  }

  if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    allStageVideos.forEach(function (video) {
      prepareMotionVideo(video);
      if (!video.classList.contains("lazy-motion-video")) playMotionVideo(video);
    });

    document.addEventListener("visibilitychange", function () {
      if (!document.hidden) {
        allStageVideos.forEach(function (video) {
          if (video.dataset.loaded === "true" || !video.classList.contains("lazy-motion-video")) {
            playMotionVideo(video);
          }
        });
      }
    });

    window.addEventListener("pageshow", function () {
      allStageVideos.forEach(function (video) {
        if (video.dataset.loaded === "true" || !video.classList.contains("lazy-motion-video")) {
          playMotionVideo(video);
        }
      });
    });

    document.addEventListener("touchstart", function resumeVideosOnFirstTouch() {
      allStageVideos.forEach(function (video) {
        if (video.dataset.loaded === "true" || !video.classList.contains("lazy-motion-video")) {
          playMotionVideo(video);
        }
      });
    }, { once:true, passive:true });
  }
});
