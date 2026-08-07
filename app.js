const categories = {
  chemistry: {
    code: "CHEMISTRY",
    name: "化学",
    description: "化学期刊、分子数据库、化学分析软件与实验学习资源。"
  },
  physics: {
    code: "PHYSICS",
    name: "物理",
    description: "物理学顶级期刊、预印本数据库、模拟工具与课程。"
  },
  math: {
    code: "MATHEMATICS",
    name: "数学",
    description: "数学期刊、数学分析、符号计算、绘图与在线学习工具。"
  },
  cs: {
    code: "COMPUTER SCIENCE",
    name: "计算机",
    description: "计算机科学期刊、编程语言官方下载、开发工具与课程。"
  },
  biology: {
    code: "BIOLOGY",
    name: "生物",
    description: "生命科学期刊、基因组数据库、生物信息学工具与课程。"
  }
};

const resources = [
  ["chemistry", "journal", "Nature Chemistry", "化学领域的重要研究成果、评论和前沿观点。", "Nature Portfolio", "付费", "https://www.nature.com/nchem/"],
  ["chemistry", "journal", "Journal of the American Chemical Society", "覆盖化学各分支的重要研究期刊。", "ACS Publications", "付费", "https://pubs.acs.org/journal/jacsat"],
  ["chemistry", "journal", "Angewandte Chemie", "国际化学研究领域的重要综合性期刊。", "Wiley-VCH", "付费", "https://onlinelibrary.wiley.com/journal/15213757"],
  ["chemistry", "journal", "Chemical Reviews", "化学领域高质量综述文章的重要来源。", "ACS Publications", "付费", "https://pubs.acs.org/journal/chreay"],
  ["chemistry", "journal", "Nature Reviews Chemistry", "化学领域的高质量综述和研究趋势。", "Nature Portfolio", "付费", "https://www.nature.com/natrevchem/"],
  ["chemistry", "journal", "Chemical Science", "英国皇家化学学会旗下开放获取化学期刊。", "RSC", "免费", "https://pubs.rsc.org/en/journals/journalissues/sc"],
  ["chemistry", "database", "PubChem", "查询化合物结构、性质、生物活性和安全信息。", "NIH", "免费", "https://pubchem.ncbi.nlm.nih.gov/"],
  ["chemistry", "database", "ChemSpider", "搜索数千万种化学结构和相关信息。", "RSC", "免费", "https://www.chemspider.com/"],
  ["chemistry", "database", "NIST Chemistry WebBook", "提供热化学、光谱、反应和物性数据。", "NIST", "免费", "https://webbook.nist.gov/chemistry/"],
  ["chemistry", "tool", "OriginLab", "用于科研绘图、数据处理、拟合和统计分析。", "科研数据分析", "付费", "https://www.originlab.com/"],
  ["chemistry", "tool", "ChemDraw", "化学结构绘制、反应式编辑和化学信息处理。", "PerkinElmer", "付费", "https://revvitysignals.com/products/research/chemdraw"],
  ["chemistry", "tool", "Avogadro", "免费开源的分子建模、结构编辑和可视化软件。", "开源软件", "免费", "https://avogadro.cc/"],
  ["chemistry", "tool", "MestReNova", "核磁共振、质谱和光谱数据分析软件。", "化学分析软件", "付费", "https://mestrelab.com/software/mnova/"],
  ["chemistry", "tool", "SDBS", "日本国立先进工业科学技术研究所光谱数据库。", "光谱分析", "免费", "https://sdbs.db.aist.go.jp/"],

  ["physics", "journal", "Nature Physics", "覆盖量子、凝聚态、粒子和天体物理。", "Nature Portfolio", "付费", "https://www.nature.com/nphys/"],
  ["physics", "journal", "Physical Review Letters", "发表物理学领域具有重要意义的研究成果。", "APS", "付费", "https://journals.aps.org/prl/"],
  ["physics", "journal", "Reviews of Modern Physics", "物理学各领域高影响力综述期刊。", "APS", "付费", "https://journals.aps.org/rmp/"],
  ["physics", "journal", "Physical Review X", "开放获取的综合物理研究期刊。", "APS", "免费", "https://journals.aps.org/prx/"],
  ["physics", "journal", "Science", "覆盖基础科学和应用科学的综合性期刊。", "AAAS", "付费", "https://www.science.org/"],
  ["physics", "journal", "Journal of High Energy Physics", "高能物理、粒子物理与场论研究期刊。", "Springer / SISSA", "付费", "https://link.springer.com/journal/13130"],
  ["physics", "database", "arXiv Physics", "物理学及相关领域的开放预印本平台。", "Cornell University", "免费", "https://arxiv.org/archive/physics"],
  ["physics", "database", "INSPIRE HEP", "高能物理论文、作者、实验和数据索引。", "CERN", "免费", "https://inspirehep.net/"],
  ["physics", "tool", "PhET Interactive Simulations", "通过互动模拟学习物理、化学和数学。", "University of Colorado", "免费", "https://phet.colorado.edu/"],
  ["physics", "tool", "Falstad Physics Applets", "包含电磁学、波动、力学和光学模拟。", "Interactive Physics", "免费", "https://www.falstad.com/mathphysics.html"],
  ["physics", "tool", "Wolfram Alpha Physics", "在线计算物理公式、单位转换和科学问题。", "Wolfram", "免费", "https://www.wolframalpha.com/"],
  ["physics", "tool", "Tracker Video Analysis", "通过视频分析研究运动、轨迹和动力学。", "Open Source Physics", "免费", "https://physlets.org/tracker/"],

  ["math", "journal", "Annals of Mathematics", "数学研究领域最具影响力的期刊之一。", "Princeton / IAS", "付费", "https://annals.math.princeton.edu/"],
  ["math", "journal", "Inventiones Mathematicae", "发表纯数学领域的重要研究成果。", "Springer", "付费", "https://link.springer.com/journal/222"],
  ["math", "journal", "Journal of the American Mathematical Society", "美国数学学会旗下的重要研究期刊。", "AMS", "付费", "https://www.ams.org/journals/jams/"],
  ["math", "journal", "Acta Mathematica", "发表纯数学领域的高水平研究论文。", "Institut Mittag-Leffler", "付费", "https://intlpress.com/site/pub/pages/journals/items/00000002/"],
  ["math", "journal", "Communications on Pure and Applied Mathematics", "纯数学和应用数学的重要研究期刊。", "Wiley", "付费", "https://onlinelibrary.wiley.com/journal/10970312"],
  ["math", "journal", "Mathematics Magazine", "面向数学教育者和数学爱好者的数学期刊。", "MAA", "付费", "https://maa.org/math-magazine/"],
  ["math", "database", "MathSciNet", "数学论文、作者和评论索引数据库。", "AMS", "付费", "https://mathscinet.ams.org/"],
  ["math", "database", "zbMATH Open", "数学及相关领域的论文和评论数据库。", "EMS", "免费", "https://zbmath.org/"],
  ["math", "tool", "Wolfram Mathematica", "用于数学分析、符号计算、微积分和建模。", "Wolfram", "付费", "https://www.wolfram.com/mathematica/"],
  ["math", "tool", "SageMath", "免费开源数学软件，支持代数、微积分和数值分析。", "Open Source", "免费", "https://www.sagemath.org/"],
  ["math", "tool", "GeoGebra", "结合几何、代数、统计和微积分的数学工具。", "GeoGebra", "免费", "https://www.geogebra.org/"],
  ["math", "tool", "Desmos", "在线绘制函数、参数方程和数据图表。", "Graphing Calculator", "免费", "https://www.desmos.com/calculator"],
  ["math", "tool", "MATLAB", "用于数学分析、矩阵计算、建模和工程计算。", "MathWorks", "付费", "https://www.mathworks.com/products/matlab.html"],
  ["math", "tool", "Wolfram Alpha", "在线求解方程、积分、极限、级数和微分问题。", "Computational Engine", "免费", "https://www.wolframalpha.com/"],

  ["cs", "journal", "Communications of the ACM", "计算机科学研究、产业趋势和技术观点。", "ACM", "付费", "https://cacm.acm.org/"],
  ["cs", "journal", "Journal of Machine Learning Research", "机器学习领域的重要开放获取研究期刊。", "JMLR", "免费", "https://www.jmlr.org/"],
  ["cs", "journal", "IEEE Transactions on Computers", "计算机体系结构、系统和计算技术研究。", "IEEE", "付费", "https://www.computer.org/csdl/journal/tc"],
  ["cs", "journal", "ACM Computing Surveys", "计算机科学各方向的高质量综述文章。", "ACM", "付费", "https://dl.acm.org/journal/csur"],
  ["cs", "journal", "Artificial Intelligence", "人工智能理论、方法和应用研究期刊。", "Elsevier", "付费", "https://www.sciencedirect.com/journal/artificial-intelligence"],
  ["cs", "journal", "IEEE TPAMI", "计算机视觉、模式识别和机器学习研究。", "IEEE", "付费", "https://www.computer.org/csdl/journal/tp"],
  ["cs", "database", "Papers with Code", "连接机器学习论文、代码、数据集和排行榜。", "Machine Learning", "免费", "https://paperswithcode.com/"],
  ["cs", "database", "DBLP", "计算机科学论文和作者的开放数据库。", "Bibliography", "免费", "https://dblp.org/"],
  ["cs", "tool", "Python", "Python 编程语言官方下载入口。", "Programming Language", "免费", "https://www.python.org/downloads/"],
  ["cs", "tool", "Java", "Java JDK 官方下载入口。", "Oracle / OpenJDK", "免费", "https://www.oracle.com/java/technologies/downloads/"],
  ["cs", "tool", "C++", "C++ 语言与标准库官方信息入口。", "ISO C++", "免费", "https://isocpp.org/get-started"],
  ["cs", "tool", "Node.js", "JavaScript 运行时官方下载入口。", "JavaScript Runtime", "免费", "https://nodejs.org/en/download"],
  ["cs", "tool", "R Project", "R 语言官方下载入口，用于统计和数据分析。", "Statistical Computing", "免费", "https://cran.r-project.org/"],
  ["cs", "tool", "PyCharm", "面向 Python 开发的集成开发环境。", "JetBrains IDE", "免费", "https://www.jetbrains.com/pycharm/download/"],
  ["cs", "tool", "Visual Studio Code", "轻量级代码编辑器，支持多种编程语言。", "Microsoft IDE", "免费", "https://code.visualstudio.com/download"],
  ["cs", "tool", "IntelliJ IDEA", "面向 Java 和 JVM 开发的集成开发环境。", "JetBrains IDE", "免费", "https://www.jetbrains.com/idea/download/"],
  ["cs", "tool", "Jupyter", "用于交互式编程、数据分析和科研计算。", "Interactive Computing", "免费", "https://jupyter.org/install"],
  ["cs", "course", "MIT OpenCourseWare", "麻省理工学院开放的编程和计算机课程。", "MIT", "免费", "https://ocw.mit.edu/search/?d=Electrical%20Engineering%20and%20Computer%20Science"],
  ["cs", "course", "CS50", "哈佛大学计算机科学入门课程。", "Harvard University", "免费", "https://cs50.harvard.edu/"],

  ["biology", "journal", "Nature", "覆盖生命科学、医学和自然科学的综合性期刊。", "Nature Portfolio", "付费", "https://www.nature.com/"],
  ["biology", "journal", "Cell", "细胞生物学、分子生物学和生命科学研究期刊。", "Cell Press", "付费", "https://www.cell.com/cell/home"],
  ["biology", "journal", "Science", "发表生命科学及其他自然科学领域的重要研究。", "AAAS", "付费", "https://www.science.org/"],
  ["biology", "journal", "Nature Genetics", "遗传学、基因组学和人类遗传研究期刊。", "Nature Portfolio", "付费", "https://www.nature.com/ng/"],
  ["biology", "journal", "Nature Methods", "生命科学实验方法、技术和工具研究期刊。", "Nature Portfolio", "付费", "https://www.nature.com/nmeth/"],
  ["biology", "journal", "PLOS Biology", "开放获取的综合性生物学研究期刊。", "PLOS", "免费", "https://journals.plos.org/plosbiology/"],
  ["biology", "database", "NCBI", "包含基因、蛋白质、文献和生物医学数据。", "National Library of Medicine", "免费", "https://www.ncbi.nlm.nih.gov/"],
  ["biology", "database", "UniProt", "蛋白质序列、功能和注释信息数据库。", "Protein Knowledgebase", "免费", "https://www.uniprot.org/"],
  ["biology", "database", "Ensembl", "基因组浏览、基因注释和比较基因组学数据库。", "EMBL-EBI", "免费", "https://www.ensembl.org/"],
  ["biology", "tool", "BLAST", "用于核酸和蛋白质序列相似性搜索。", "NCBI", "免费", "https://blast.ncbi.nlm.nih.gov/Blast.cgi"],
  ["biology", "tool", "Primer-BLAST", "设计并检查 PCR 引物的在线工具。", "NCBI", "免费", "https://www.ncbi.nlm.nih.gov/tools/primer-blast/"],
  ["biology", "tool", "UCSC Genome Browser", "浏览基因组、注释、变异和基因组轨道。", "Genome Browser", "免费", "https://genome.ucsc.edu/"],
  ["biology", "tool", "Galaxy", "面向生物信息学分析的在线工作流平台。", "Bioinformatics", "免费", "https://usegalaxy.org/"],
  ["biology", "tool", "AlphaFold Database", "查询人工智能预测的蛋白质三维结构。", "Protein Structure", "免费", "https://alphafold.ebi.ac.uk/"],
  ["biology", "course", "Khan Academy Biology", "从细胞、遗传到生态学的基础生物课程。", "Online Course", "免费", "https://www.khanacademy.org/science/biology"]
].map((item, index) => ({
  id: index,
  category: item[0],
  kind: item[1],
  name: item[2],
  description: item[3],
  meta: item[4],
  access: item[5],
  url: item[6]
}));

const formulas = [
  ["chemistry", "物质的量", "n = m / M", "物质的量等于质量除以摩尔质量。"],
  ["chemistry", "理想气体方程", "PV = nRT", "描述理想气体的状态关系。"],
  ["chemistry", "摩尔浓度", "c = n / V", "物质的量浓度等于物质的量除以体积。"],
  ["chemistry", "质量分数", "w = mₛ / m", "溶质质量与溶液总质量的比值。"],
  ["chemistry", "pH 定义", "pH = −log[H⁺]", "表示溶液酸碱性的基本公式。"],
  ["chemistry", "能斯特方程", "E = E° − RT/nF ln Q", "计算非标准条件下的电极电势。"],
  ["chemistry", "阿伦尼乌斯方程", "k = Ae^(−Ea/RT)", "描述反应速率常数与温度的关系。"],
  ["chemistry", "吉布斯自由能", "ΔG = ΔH − TΔS", "判断恒温恒压条件下的自发性。"],
  ["chemistry", "亨利定律", "C = kH P", "气体在液体中的溶解度关系。"],
  ["chemistry", "比尔-朗伯定律", "A = εbc", "描述吸光度与浓度之间的关系。"],

  ["physics", "牛顿第二定律", "F = ma", "合力等于质量乘以加速度。"],
  ["physics", "万有引力定律", "F = Gm₁m₂ / r²", "描述物体之间的引力关系。"],
  ["physics", "动能", "Ek = ½mv²", "物体由于运动所具有的能量。"],
  ["physics", "动量", "p = mv", "质量与速度的乘积。"],
  ["physics", "质能关系", "E = mc²", "质量与能量之间的等价关系。"],
  ["physics", "库仑定律", "F = kq₁q₂ / r²", "描述点电荷之间的静电力。"],
  ["physics", "欧姆定律", "V = IR", "电压、电流和电阻的基本关系。"],
  ["physics", "麦克斯韦方程", "∇·E = ρ/ε₀", "描述电磁场的基本方程体系。"],
  ["physics", "简谐运动", "x = A cos(ωt + φ)", "描述理想周期振动。"],
  ["physics", "薛定谔方程", "iℏ ∂ψ/∂t = Ĥψ", "描述量子系统随时间的演化。"],

  ["math", "欧拉恒等式", "e^(iπ) + 1 = 0", "联系多个基本数学常数。"],
  ["math", "勾股定理", "a² + b² = c²", "直角三角形的基本关系。"],
  ["math", "二项式定理", "(a+b)ⁿ = Σ C(n,k)aⁿ⁻ᵏbᵏ", "展开非负整数次二项式。"],
  ["math", "微积分基本定理", "∫ₐᵇ f(x)dx = F(b) − F(a)", "连接定积分和原函数。"],
  ["math", "泰勒展开", "f(x)=Σ f⁽ⁿ⁾(a)(x−a)ⁿ/n!", "用导数表示函数的局部展开。"],
  ["math", "欧拉公式", "e^(ix) = cos x + i sin x", "连接指数函数和三角函数。"],
  ["math", "傅里叶变换", "F(ω)=∫ f(t)e^(−iωt)dt", "将时域函数转换到频域。"],
  ["math", "高斯积分", "∫₋∞^∞ e^(−x²)dx = √π", "分析学和概率论中的重要积分。"],
  ["math", "贝叶斯公式", "P(A|B)=P(B|A)P(A)/P(B)", "根据证据更新事件概率。"],
  ["math", "拉格朗日乘数法", "∇f = λ∇g", "求带约束条件的函数极值。"],

  ["cs", "信息熵", "H(X)=−Σp(x)log p(x)", "衡量随机变量的不确定性。"],
  ["cs", "贝叶斯定理", "P(A|B)=P(B|A)P(A)/P(B)", "根据新证据更新概率。"],
  ["cs", "梯度下降", "θ ← θ − α∇J(θ)", "沿梯度下降方向更新模型参数。"],
  ["cs", "时间复杂度", "T(n) = O(f(n))", "描述算法随输入规模增长的速度。"],
  ["cs", "二叉搜索树", "T(n) = O(log n)", "平衡搜索树的典型查找复杂度。"],
  ["cs", "香农信道容量", "C = B log₂(1 + S/N)", "噪声信道的信息传输理论上限。"],
  ["cs", "RSA 模运算", "c = mᵉ mod n", "RSA 公钥密码体系的核心关系。"],
  ["cs", "逻辑回归", "σ(z)=1/(1+e^(−z))", "将线性输出映射为概率。"],
  ["cs", "卷积运算", "(f*g)(t)=∫f(τ)g(t−τ)dτ", "用于信号处理和卷积神经网络。"],
  ["cs", "反向传播", "∂L/∂w = ∂L/∂y · ∂y/∂w", "使用链式法则计算网络梯度。"]
].map((item) => ({
  category: item[0],
  title: item[1],
  expression: item[2],
  description: item[3]
}));

const text = {
  zh: {
    home: "首页",
    formulas: "公式库",
    back: "← 返回学科目录",
    backHome: "← 返回首页",
    all: "全部",
    journal: "期刊 / 出版物",
    database: "数据库",
    tool: "工具 / 软件",
    course: "课程 / 学习",
    open: "访问官网",
    resources: "项资源",
    search: "搜索资源名称、简介或关键词",
    noResult: "没有找到匹配的资源"
  },
  en: {
    home: "Home",
    formulas: "Formulas",
    back: "← Back to subjects",
    backHome: "← Back home",
    all: "All",
    journal: "Journals",
    database: "Databases",
    tool: "Tools / Software",
    course: "Courses",
    open: "Open website",
    resources: "resources",
    search: "Search resources",
    noResult: "No matching resources"
  }
};

let language = localStorage.getItem("aterl-language") || "zh";
let selectedCategory = null;
let favorites = JSON.parse(
  localStorage.getItem("aterl-favorites") || "[]"
);

const $ = (id) => document.getElementById(id);

function showView(id) {
  document.querySelectorAll(".view").forEach((view) => {
    view.classList.remove("active");
  });

  $(id).classList.add("active");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function kindName(kind) {
  const current = text[language];

  if (kind === "journal") return current.journal;
  if (kind === "database") return current.database;
  if (kind === "tool") return current.tool;
  if (kind === "course") return current.course;

  return kind;
}

function renderCategories() {
  $("categoryGrid").innerHTML = Object.entries(categories)
    .map(([key, item]) => {
      const count = resources.filter(
        (resource) => resource.category === key
      ).length;

      return `
        <button class="category-button" data-category="${key}">
          <span class="category-code">${item.code}</span>
          <h3>${item.name}</h3>
          <p>${count} 项资源 · 点击进入</p>
        </button>
      `;
    })
    .join("");

  document.querySelectorAll(".category-button").forEach((button) => {
    button.addEventListener("click", () => {
      openCategory(button.dataset.category);
    });
  });
}

function openCategory(category) {
  selectedCategory = category;

  $("categoryKicker").textContent =
    `CATEGORY / ${categories[category].code}`;
  $("categoryName").textContent = categories[category].name;
  $("categoryDescriptionDetail").textContent =
    categories[category].description;

  $("resourceSearch").value = "";
  $("resourceKind").value = "all";
  $("resourceAccess").value = "all";

  renderResources();
  showView("categoryView");
}

function renderResources() {
  const current = text[language];
  const query = $("resourceSearch").value.toLowerCase();
  const kind = $("resourceKind").value;
  const access = $("resourceAccess").value;

  const result = resources.filter((resource) => {
    const sameCategory = resource.category === selectedCategory;
    const sameKind = kind === "all" || resource.kind === kind;
    const sameAccess =
      access === "all" ||
      (access === "free" && resource.access === "免费") ||
      (access === "paid" && resource.access === "付费");

    const searchable = [
      resource.name,
      resource.description,
      resource.meta,
      resource.access
    ].join(" ").toLowerCase();

    return sameCategory && sameKind && sameAccess &&
      searchable.includes(query);
  });

  $("resourceCount").textContent =
    `${result.length} ${current.resources}`;

  if (!result.length) {
    $("resourceGrid").innerHTML =
      `<div class="empty">${current.noResult}</div>`;
    return;
  }

  $("resourceGrid").innerHTML = result.map((resource) => {
    const saved = favorites.includes(resource.name);

    return `
      <article class="resource-card">
        <div class="resource-card-top">
          <span class="resource-type">${kindName(resource.kind)}</span>
          <button
            class="favorite ${saved ? "active" : ""}"
            data-name="${resource.name}"
          >${saved ? "★" : "☆"}</button>
        </div>

        <h3>${resource.name}</h3>
        <p>${resource.description}</p>

        <div class="resource-meta">
          <span>${resource.meta}</span>
          <span>${resource.access}</span>
        </div>

        <div class="resource-footer">
          <span class="resource-label">
            ${categories[resource.category].name}
          </span>

          <a
            class="resource-link"
            href="${resource.url}"
            target="_blank"
            rel="noopener noreferrer"
          >${current.open} ↗</a>
        </div>
      </article>
    `;
  }).join("");

  document.querySelectorAll(".favorite").forEach((button) => {
    button.addEventListener("click", () => {
      const name = button.dataset.name;

      if (favorites.includes(name)) {
        favorites = favorites.filter((item) => item !== name);
      } else {
        favorites.push(name);
      }

      localStorage.setItem(
        "aterl-favorites",
        JSON.stringify(favorites)
      );

      renderResources();
    });
  });
}

function renderFormulas(category = "all") {
  const list = category === "all"
    ? formulas
    : formulas.filter((formula) => formula.category === category);

  $("formulaGrid").innerHTML = list.map((formula) => `
    <article class="formula-card">
      <div class="formula-category">
        ${categories[formula.category].code}
      </div>

      <h3>${formula.title}</h3>

      <div class="formula-expression">
        ${formula.expression}
      </div>

      <p>${formula.description}</p>
      <span class="formula-use">
        ${categories[formula.category].name} · 基础公式
      </span>
    </article>
  `).join("");
}

function applyLanguage() {
  const current = text[language];

  $("brandSubtitle").textContent =
    language === "zh"
      ? "理工科研究与学习资源中心"
      : "Science research and learning directory";

  $("heroTitle").textContent =
    language === "zh"
      ? "理工科资源，集中在一个清晰的入口。"
      : "A clear entrance to science resources.";

  $("heroDescription").textContent =
    language === "zh"
      ? "面向学生、研究者和技术实践者的学术资源导航。从期刊、数据库到分析软件与编程工具，按学科快速进入。"
      : "A practical directory for students, researchers and technical practitioners.";

  $("categoryTitle").textContent =
    language === "zh" ? "选择学科" : "Choose a subject";

  $("categoryDescription").textContent =
    language === "zh"
      ? "进入对应学科的期刊、工具和学习资源。"
      : "Browse journals, tools and learning resources by subject.";

  $("homeButton").textContent = current.home;
  $("formulaButton").textContent = current.formulas;
  $("backButton").textContent = current.back;
  $("formulaBackButton").textContent = current.backHome;
  $("categoryFormulaButton").textContent = current.formulas;
  $("resourceSearch").placeholder = current.search;

  $("languageButton").textContent =
    language === "zh" ? "EN" : "中文";

  renderCategories();
  renderFormulas();

  if (selectedCategory) {
    renderResources();
  }
}

$("homeButton").addEventListener("click", () => {
  selectedCategory = null;
  showView("homeView");
});

$("formulaButton").addEventListener("click", () => {
  renderFormulas();
  showView("formulaView");
});

$("backButton").addEventListener("click", () => {
  selectedCategory = null;
  showView("homeView");
});

$("formulaBackButton").addEventListener("click", () => {
  showView("homeView");
});

$("categoryFormulaButton").addEventListener("click", () => {
  renderFormulas(selectedCategory);
  showView("formulaView");
});

$("resourceSearch").addEventListener("input", renderResources);
$("resourceKind").addEventListener("change", renderResources);
$("resourceAccess").addEventListener("change", renderResources);

$("languageButton").addEventListener("click", () => {
  language = language === "zh" ? "en" : "zh";
  localStorage.setItem("aterl-language", language);
  applyLanguage();
});

document.querySelectorAll(".formula-filter").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".formula-filter").forEach((item) => {
      item.classList.remove("active");
    });

    button.classList.add("active");
    renderFormulas(button.dataset.formulaCategory);
  });
});

applyLanguage();
showView("homeView");