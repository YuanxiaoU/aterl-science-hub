/* ==========================================================
   交互特效：鼠标视差 / 时间轴进度 / 全球部署图
   ========================================================== */
(function () {
  "use strict";

  /* ---------------- 1. 鼠标视差（线性跟随，桌面端）---------------- */
  function initParallax() {
    var hero = document.getElementById("hero");
    var layers = document.querySelectorAll("[data-depth]");
    if (!hero || !layers.length) return;
    if (!window.matchMedia("(hover: hover) and (pointer: fine)").matches) return; // 触屏禁用

    var target = { x: 0, y: 0 };
    var current = { x: 0, y: 0 };

    hero.addEventListener("mousemove", function (e) {
      var r = hero.getBoundingClientRect();
      target.x = ((e.clientX - r.left) / r.width - 0.5) * 2;   // -1 .. 1
      target.y = ((e.clientY - r.top) / r.height - 0.5) * 2;
    });
    hero.addEventListener("mouseleave", function () {
      target.x = 0; target.y = 0;
    });

    function tick() {
      current.x += (target.x - current.x) * 0.06;
      current.y += (target.y - current.y) * 0.06;
      for (var i = 0; i < layers.length; i++) {
        var el = layers[i];
        var d = parseFloat(el.getAttribute("data-depth")) || 0;
        var mx = current.x * d * 30;   // 最大位移 ~30px
        var my = current.y * d * 30;
        el.style.transform = "translate3d(" + mx.toFixed(2) + "px," + my.toFixed(2) + "px,0)";
      }
      requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }

  /* ---------------- 2. 时间轴进度线 ---------------- */
  function initTimeline() {
    var sec = document.getElementById("journey");
    var fill = document.getElementById("timelineFill");
    if (!sec || !fill) return;

    function update() {
      var r = sec.getBoundingClientRect();
      var vh = window.innerHeight || document.documentElement.clientHeight;
      var total = sec.offsetHeight - vh * 0.5;
      if (total <= 0) total = 1;
      var passed = vh * 0.6 - r.top;      // 距视口 60% 处开始
      var p = Math.max(0, Math.min(1, passed / total));
      fill.style.height = (p * 100) + "%";
    }
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    update();
  }

  /* ---------------- 3. 全球部署图（点阵世界地图 + 节点）---------------- */
  function initMap() {
    var host = document.getElementById("worldMap");
    if (!host) return;

    // 陆地矩形（归一化坐标：x 0-100，y 0-52，y 越小越北）
    var lands = [
      [24, 8, 29, 12],    // 格陵兰
      [8, 10, 13, 15],    // 阿拉斯加
      [12, 13, 32, 24],   // 北美
      [21, 24, 25, 27],   // 中美
      [25, 27, 34, 46],   // 南美
      [41, 10, 43, 12],   // 英伦
      [47, 7, 51, 11],    // 北欧
      [43, 11, 49, 18],   // 欧洲
      [43, 19, 53, 38],   // 非洲
      [53, 20, 59, 26],   // 中东
      [50, 6, 82, 20],    // 俄罗斯/北亚
      [58, 22, 63, 28],   // 印度
      [63, 12, 76, 22],   // 东亚/中国
      [68, 24, 74, 28],   // 东南亚
      [66, 29, 73, 30],   // 印尼
      [80, 15, 82, 19],   // 日本
      [74, 32, 86, 40],   // 澳洲
      [86, 40, 88, 43]    // 新西兰
    ];

    function inLand(x, y) {
      for (var i = 0; i < lands.length; i++) {
        var l = lands[i];
        if (x >= l[0] && x <= l[2] && y >= l[1] && y <= l[3]) return true;
      }
      return false;
    }

    var NS = "http://www.w3.org/2000/svg";
    var svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", "0 0 100 52");
    svg.setAttribute("role", "img");
    svg.style.display = "block";
    svg.style.width = "100%";
    svg.style.height = "auto";

    // 陆地圆点
    var step = 1.6, r = 0.62;
    for (var y = 2; y <= 50; y += step) {
      for (var x = 1; x <= 99; x += step) {
        if (inLand(x, y)) {
          var c = document.createElementNS(NS, "circle");
          c.setAttribute("cx", x);
          c.setAttribute("cy", y);
          c.setAttribute("r", r);
          c.setAttribute("fill", "rgba(148,180,220,0.30)");
          svg.appendChild(c);
        }
      }
    }

    // 节点（示意本地部署能力，非真实客户）
    var nodes = [
      [68, 17],   // 东亚
      [46, 14],   // 欧洲
      [20, 17],   // 北美
      [30, 33],   // 南美
      [80, 36]    // 澳洲
    ];
    var nodeG = document.createElementNS(NS, "g");
    for (var i = 0; i < nodes.length; i++) {
      var g = document.createElementNS(NS, "g");
      g.setAttribute("class", "map-node");
      var halo = document.createElementNS(NS, "circle");
      halo.setAttribute("cx", nodes[i][0]);
      halo.setAttribute("cy", nodes[i][1]);
      halo.setAttribute("r", 1.6);
      halo.setAttribute("class", "map-halo");
      halo.setAttribute("fill", "rgba(46,124,246,0.25)");
      var core = document.createElementNS(NS, "circle");
      core.setAttribute("cx", nodes[i][0]);
      core.setAttribute("cy", nodes[i][1]);
      core.setAttribute("r", 0.55);
      core.setAttribute("fill", "#6FA8FF");
      g.appendChild(halo);
      g.appendChild(core);
      nodeG.appendChild(g);
    }
    svg.appendChild(nodeG);

    host.appendChild(svg);
  }

  initParallax();
  initTimeline();
  initMap();
})();
