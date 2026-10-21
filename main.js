/* ==========================================================
   Aterl-DistSim 官网脚本：中英文切换 / 滚动动画 / 数字滚动 /
   进度条动画 / 模块截图切换 / 顶栏阴影
   ========================================================== */
(function () {
  "use strict";

  /* ---------------- i18n ---------------- */
  var I18N = {
    zh: {
      "nav.results": "核心成果",
      "nav.journey": "改进历程",
      "nav.arch": "系统架构",
      "nav.download": "开源下载",
      "nav.cta": "免费下载",

      "hero.eyebrow": "Aterl-DistSim · 精馏装置仿真与控制系统",
      "hero.title": "让大模型，安全地走进精馏控制",
      "hero.sub": "Aterl-DistSim 以乙醇–水精馏装置为对象，通过「三重约束提示 + 确定性方向翻转 + ESD 硬联锁」的分层防线，让本地轻量化大模型以监督者身份安全介入流程工业控制。",
      "hero.cta1": "免费下载 V1.0",
      "hero.cta2": "查看核心成果",
      "hero.trust": "31 典型工况 · 16 仿真设备 · 6 控制回路 · 本地部署 · 开源学习项目",
      "hero.scroll": "向下滚动探索",

      "shot.dcs": "DCS 监控",
      "shot.panel": "控制面板",
      "shot.dcsAlt": "Aterl-DistSim DCS 监控界面：精馏工段 DCS 流程图",
      "shot.panelAlt": "Aterl-DistSim 控制面板：温度、压力与液位趋势曲线",

      "stats.s1": "典型实验工况",
      "stats.s2": "仿真设备",
      "stats.s3": "控制回路",

      "intro.eyebrow": "系统介绍",
      "intro.title": "一套系统，四种核心能力",
      "intro.sub": "面向精馏生产装置，提供仿真、监控、AI 顾问与自动实验的一体化能力，双模式共用同一套界面。",
      "cap1.title": "动态工艺仿真",
      "cap1.desc": "基于乙醇–水体系的动态机理仿真，覆盖 31 个典型工况，逼真还原精馏全过程。",
      "cap2.title": "真实 PLC 监控",
      "cap2.desc": "通过 Snap7 与 S7-1200 实机互联，16 台设备的实时状态尽收眼底。",
      "cap3.title": "AI 智能操作顾问",
      "cap3.desc": "本地轻量化大模型实时解读工况，给出可解释的操作建议，人始终在环。",
      "cap4.title": "自动化实验采集",
      "cap4.desc": "一键批量运行实验工况，自动采集、记录与导出数据。",

      "method.eyebrow": "改进历程",
      "method.title": "一步步改进，直到安全可控",
      "method.sub": "从\"直接下指令\"到\"分层防线\"，方向正确率由 16.1% 提升到 91.4%。",
      "journey.eyebrow": "改进历程",
      "journey.title": "一步步改进，直到安全可控",
      "journey.sub": "从\"直接下指令\"到\"分层防线\"，方向正确率由 16.1% 提升到 91.4%。",
      "tl1.stage": "起点 · 直接指令",
      "tl1.title": "让大模型直接下指令",
      "tl1.desc": "未经约束的大模型直接输出控制动作，方向正确率仅 16.1%，安全风险不可控。",
      "tl2.stage": "第一步 · 三重约束提示",
      "tl2.title": "用提示工程框住输出",
      "tl2.desc": "以角色、知识、安全三重约束框定每一次输出，把回答限制在工艺允许范围之内。",
      "tl3.stage": "第二步 · 确定性方向翻转",
      "tl3.title": "对方向做确定性校验",
      "tl3.desc": "对模型给出的控制方向做确定性校验，25 个方向错误样本全部纠正。",
      "tl4.stage": "第三步 · ESD 硬联锁",
      "tl4.title": "物理层兜底",
      "tl4.desc": "双层紧急停车独立于软件运行，即便 AI 失效，硬件层仍能第一时间保护装置。",
      "tl5.stage": "成果",
      "tl5.title": "安全，可用，可控",
      "tl5.desc": "方向正确率 91.4%，错误动作下发 0，大模型以监督者身份安全介入精馏控制。",
      "tl.acc": "方向正确率",

      "results.eyebrow": "核心成果",
      "results.title": "用数据说话：安全性显著提升",
      "results.sub": "在 31 个典型工况下完成对比验证，方向正确率由 16.1% 提升至 91.4%，错误动作下发为零。",
      "chart.title": "方向正确率对比",
      "chart.bar1": "传统大模型方案",
      "chart.bar2": "Aterl-DistSim",
      "chart.note": "31 个典型工况对比验证 · 以方向正确率为核心评价指标",
      "met1.label": "方向正确率（提升后）",
      "met2.label": "正确率提升幅度",
      "met3.label": "方向错误全部纠正",
      "met4.label": "错误动作下发",

      "arch.eyebrow": "系统架构",
      "arch.title": "四层协同，层层设防",
      "arch.sub": "从交互层到设备层，每一层职责清晰、边界明确，共同构成一套完整的闭环控制系统。",
      "layer1.name": "交互层",
      "layer1.desc": "桌面应用界面，双模式一键切换，操作员与工程师共用一套视图。",
      "layer2.name": "业务层",
      "layer2.desc": "仿真引擎、PLC 通信、AI 顾问与自动实验四大核心业务模块。",
      "layer3.name": "智能层",
      "layer3.desc": "本地轻量化大模型推理，无云端依赖，数据不出厂。",
      "layer4.name": "设备层",
      "layer4.desc": "S7-1200 PLC 与精馏装置实机互联，Snap7 协议通信。",

      "dl.eyebrow": "开源下载",
      "dl.title": "获取 Aterl-DistSim",
      "dl.sub": "源码与安装包全部开放，遵循 Apache-2.0 许可，免费使用，无任何商业行为。",
      "dl1.title": "源码仓库",
      "dl1.desc": "完整源码、架构文档与使用说明，可自由 clone、fork 与二次开发。",
      "dl1.btn": "前往 GitHub 仓库",
      "dl2.title": "Windows 安装包",
      "dl2.desc": "开箱即用的桌面客户端，内置本地大模型运行时，双击即可安装。",
      "dl2.btn": "从 GitHub 下载",
      "dl2.hint": "308 MB · V1.0 · 本地部署",
      "tech.label": "技术栈",

      "map.eyebrow": "本地部署",
      "map.title": "跑在本地，数据不出厂",
      "map.sub": "无云端依赖，任意工厂、实验室都能本地运行，工艺数据始终留在厂区。",
      "map.c1": "本地推理",
      "map.c2": "离线运行",
      "map.c3": "数据不出厂",
      "map.note": "* 开源学习项目 · 示意：可在任意地点本地部署",

      "contact.title": "问题反馈与交流",
      "contact.desc": "本项目为开源学习项目，欢迎在 GitHub 仓库提交 Issue 交流。",

      "footer.copyright": "© 2026 ATERL · Aterl-DistSim",
      "footer.license": "Apache-2.0 License",
      "footer.nonprofit": "本网站为个人非经营性网站，仅用于开源技术学习交流，不含任何商业行为。"
    },

    en: {
      "nav.results": "Results",
      "nav.journey": "Journey",
      "nav.arch": "Architecture",
      "nav.download": "Download",
      "nav.cta": "Download",

      "hero.eyebrow": "Aterl-DistSim · Distillation Simulation & Control System",
      "hero.title": "Let LLMs step into distillation control — safely",
      "hero.sub": "Aterl-DistSim targets an ethanol–water distillation unit. Through layered defenses — triple-constraint prompting, deterministic direction flip, and ESD hard interlock — a local lightweight LLM safely joins process control as a supervisor.",
      "hero.cta1": "Download V1.0",
      "hero.cta2": "View Results",
      "hero.trust": "31 benchmark cases · 16 simulated units · 6 control loops · Local deployment · Open-source learning project",
      "hero.scroll": "Scroll to explore",

      "shot.dcs": "DCS Overview",
      "shot.panel": "Control Panel",
      "shot.dcsAlt": "Aterl-DistSim DCS overview: distillation unit flow diagram",
      "shot.panelAlt": "Aterl-DistSim control panel: temperature, pressure and level trends",

      "stats.s1": "Benchmark cases",
      "stats.s2": "Simulated units",
      "stats.s3": "Control loops",

      "intro.eyebrow": "Overview",
      "intro.title": "One system, four core capabilities",
      "intro.sub": "Built for distillation units, integrating simulation, monitoring, an AI advisor, and automated experiments — two modes, one interface.",
      "cap1.title": "Dynamic Process Simulation",
      "cap1.desc": "Dynamic first-principles simulation of the ethanol–water system across 31 benchmark cases.",
      "cap2.title": "Real PLC Monitoring",
      "cap2.desc": "Connected to a real S7-1200 PLC via Snap7, with live status of 16 units at a glance.",
      "cap3.title": "AI Operation Advisor",
      "cap3.desc": "A local lightweight LLM interprets conditions in real time and explains its suggestions — humans always in the loop.",
      "cap4.title": "Automated Experiments",
      "cap4.desc": "Run benchmark batches with one click and collect data automatically.",

      "method.eyebrow": "The Journey",
      "method.title": "Improved step by step, until safety is assured",
      "method.sub": "From raw commands to layered defenses, direction accuracy rose from 16.1% to 91.4%.",
      "journey.eyebrow": "The Journey",
      "journey.title": "Improved step by step, until safety is assured",
      "journey.sub": "From raw commands to layered defenses, direction accuracy rose from 16.1% to 91.4%.",
      "tl1.stage": "Start · Raw commands",
      "tl1.title": "Letting the LLM give commands directly",
      "tl1.desc": "An unconstrained LLM issued control actions directly; direction accuracy was only 16.1%, with unacceptable risk.",
      "tl2.stage": "Step 1 · Triple-constraint prompting",
      "tl2.title": "Bounding outputs with prompt engineering",
      "tl2.desc": "Role, knowledge, and safety constraints bound every output within process limits.",
      "tl3.stage": "Step 2 · Deterministic direction flip",
      "tl3.title": "Deterministically verifying direction",
      "tl3.desc": "Every control direction is deterministically checked; all 25 misdirected samples were corrected.",
      "tl4.stage": "Step 3 · ESD hard interlock",
      "tl4.title": "A hardware safety net",
      "tl4.desc": "Dual emergency shutdown runs independently of the software, protecting the unit even if AI fails.",
      "tl5.stage": "Result",
      "tl5.title": "Safe, usable, controllable",
      "tl5.desc": "91.4% direction accuracy with zero erroneous commands — the LLM safely joins distillation control as a supervisor.",
      "tl.acc": "Direction accuracy",

      "results.eyebrow": "Results",
      "results.title": "The numbers speak: a major safety upgrade",
      "results.sub": "Verified across 31 benchmark cases: direction accuracy rose from 16.1% to 91.4%, with zero erroneous commands issued.",
      "chart.title": "Direction accuracy comparison",
      "chart.bar1": "Baseline LLM",
      "chart.bar2": "Aterl-DistSim",
      "chart.note": "31 benchmark cases · direction accuracy as the core metric",
      "met1.label": "Direction accuracy (after)",
      "met2.label": "Accuracy improvement",
      "met3.label": "Misdirected samples corrected",
      "met4.label": "Erroneous commands issued",

      "arch.eyebrow": "Architecture",
      "arch.title": "Four layers, defense in depth",
      "arch.sub": "From UI to devices, every layer has a clear responsibility and boundary, forming a complete closed loop.",
      "layer1.name": "UI Layer",
      "layer1.desc": "Desktop interface with one-click mode switching, shared by operators and engineers.",
      "layer2.name": "Business Layer",
      "layer2.desc": "Four core modules: simulation engine, PLC communication, AI advisor, and automated experiments.",
      "layer3.name": "Intelligence Layer",
      "layer3.desc": "Local lightweight LLM inference with no cloud dependency; data never leaves the plant.",
      "layer4.name": "Device Layer",
      "layer4.desc": "S7-1200 PLC connected to the real unit over the Snap7 protocol.",

      "dl.eyebrow": "Download",
      "dl.title": "Get Aterl-DistSim",
      "dl.sub": "Fully open source under Apache-2.0 — free to use, non-commercial.",
      "dl1.title": "Source Repository",
      "dl1.desc": "Full source code, architecture docs, and user manual. Clone, fork, and build on it freely.",
      "dl1.btn": "View on GitHub",
      "dl2.title": "Windows Installer",
      "dl2.desc": "Ready-to-run desktop client with a built-in local LLM runtime.",
      "dl2.btn": "Download from GitHub",
      "dl2.hint": "308 MB · V1.0 · Local deployment",
      "tech.label": "Tech Stack",

      "map.eyebrow": "Local Deployment",
      "map.title": "Runs locally, data stays on-site",
      "map.sub": "No cloud dependency — run it at any plant or lab, and process data never leaves the facility.",
      "map.c1": "Local inference",
      "map.c2": "Offline operation",
      "map.c3": "Data stays on-site",
      "map.note": "* Open-source learning project · illustrative: deployable locally anywhere",

      "contact.title": "Feedback & Contact",
      "contact.desc": "This is an open-source learning project. Feel free to open an issue on GitHub.",

      "footer.copyright": "© 2026 ATERL · Aterl-DistSim",
      "footer.license": "Apache-2.0 License",
      "footer.nonprofit": "This is a personal, non-commercial website for open-source learning purposes only."
    }
  };

  var TITLES = {
    zh: "Aterl",
    en: "Aterl"
  };

  var LANG_KEY = "aterl-lang";

  function getLang() {
    try { return localStorage.getItem(LANG_KEY) || "zh"; } catch (e) { return "zh"; }
  }

  function setLang(lang) {
    try { localStorage.setItem(LANG_KEY, lang); } catch (e) { /* ignore */ }
    document.documentElement.setAttribute("lang", lang === "zh" ? "zh-CN" : "en");
    document.title = TITLES[lang];
    var dict = I18N[lang];
    var nodes = document.querySelectorAll("[data-i18n]");
    for (var i = 0; i < nodes.length; i++) {
      var key = nodes[i].getAttribute("data-i18n");
      if (dict[key] !== undefined) nodes[i].innerHTML = dict[key];
    }
    var alts = document.querySelectorAll("[data-i18n-alt]");
    for (var j = 0; j < alts.length; j++) {
      var akey = alts[j].getAttribute("data-i18n-alt");
      if (dict[akey] !== undefined) alts[j].setAttribute("alt", dict[akey]);
    }
    var spans = document.querySelectorAll(".lang-toggle span");
    for (var k = 0; k < spans.length; k++) {
      spans[k].classList.toggle("active", spans[k].getAttribute("data-lang") === lang);
    }
  }

  document.getElementById("langToggle").addEventListener("click", function () {
    setLang(getLang() === "zh" ? "en" : "zh");
  });

  setLang(getLang());

  /* ---------------- 顶栏滚动阴影 + 阅读进度条 ---------------- */
  var header = document.querySelector(".site-header");
  var progressBar = document.getElementById("progressBar");
  function onScroll() {
    if (window.scrollY > 8) header.classList.add("scrolled");
    else header.classList.remove("scrolled");
    if (progressBar) {
      var doc = document.documentElement;
      var max = doc.scrollHeight - doc.clientHeight;
      var p = max > 0 ? (window.scrollY / max) * 100 : 0;
      progressBar.style.width = p + "%";
    }
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  /* ---------------- 模块截图切换 ---------------- */
  var shotImg = document.getElementById("shotImg");
  var SHOTS = { dcs: "assets/app-dcs.jpg", panel: "assets/app-panel.jpg" };
  // 预加载，保证切换无闪烁
  Object.keys(SHOTS).forEach(function (k) { var im = new Image(); im.src = SHOTS[k]; });

  var tabs = document.querySelectorAll(".shot-tab");
  for (var t = 0; t < tabs.length; t++) {
    tabs[t].addEventListener("click", function () {
      var tab = this;
      if (tab.classList.contains("active")) return;
      for (var i = 0; i < tabs.length; i++) tabs[i].classList.remove("active");
      tab.classList.add("active");
      var src = SHOTS[tab.getAttribute("data-shot")];
      shotImg.classList.add("fading");
      setTimeout(function () {
        shotImg.src = src;
        var done = function () { shotImg.classList.remove("fading"); };
        if (shotImg.complete) done();
        else { shotImg.onload = done; shotImg.onerror = done; }
      }, 220);
    });
  }

  /* ---------------- 数字滚动 ---------------- */
  function animateCount(el) {
    var target = parseFloat(el.getAttribute("data-count")) || 0;
    var decimals = parseInt(el.getAttribute("data-decimals") || "0", 10);
    var prefix = el.getAttribute("data-prefix") || "";
    var suffix = el.getAttribute("data-suffix") || "";
    var dur = 1400;
    var start = null;
    function frame(now) {
      if (start === null) start = now;
      var p = Math.min((now - start) / dur, 1);
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = prefix + (target * eased).toFixed(decimals) + suffix;
      if (p < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }

  /* ---------------- 滚动入场 + 触发图表/数字 ---------------- */
  function runCounters(scope) {
    var nums = scope.querySelectorAll("[data-count]");
    for (var i = 0; i < nums.length; i++) animateCount(nums[i]);
  }

  function fillBars(scope) {
    var bars = scope.querySelectorAll(".bar-fill");
    for (var i = 0; i < bars.length; i++) {
      (function (bar) {
        requestAnimationFrame(function () {
          bar.style.width = bar.getAttribute("data-w") + "%";
        });
      })(bars[i]);
    }
  }

  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        var el = en.target;
        el.classList.add("visible");
        runCounters(el);
        fillBars(el);
        io.unobserve(el);
      });
    }, { threshold: 0.18 });

    var reveals = document.querySelectorAll(".reveal");
    for (var r = 0; r < reveals.length; r++) io.observe(reveals[r]);
  } else {
    // 兜底：直接显示
    var all = document.querySelectorAll(".reveal");
    for (var a = 0; a < all.length; a++) {
      all[a].classList.add("visible");
      runCounters(all[a]);
      fillBars(all[a]);
    }
  }
  // 区块级动效：同组元素依次进场 + 每个 section 顶边"刷新"扫描一次
  (function initBlockMotion() {
    if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    var groups = document.querySelectorAll(".container, .grid-4, .grid-3, .stats-row");
    for (var g = 0; g < groups.length; g++) {
      var kids = groups[g].children;
      var idx = 0;
      for (var k = 0; k < kids.length; k++) {
        var el = kids[k];
        if (!el.classList || !el.classList.contains("reveal")) continue;
        if (!el.style.getPropertyValue("--d")) {
          el.style.setProperty("--d", idx * 80 + "ms");
        }
        idx++;
      }
    }

    var sections = document.querySelectorAll(".section");
    if (!("IntersectionObserver" in window)) {
      for (var s = 0; s < sections.length; s++) sections[s].classList.add("scan");
      return;
    }
    var sio = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        en.target.classList.add("scan");
        sio.unobserve(en.target);
      });
    }, { threshold: 0.12 });
    for (var i = 0; i < sections.length; i++) sio.observe(sections[i]);
  })();
})();
