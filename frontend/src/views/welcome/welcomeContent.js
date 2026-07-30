// Welcome page static content — single source of truth for all visible copy and demo data.
// Components receive content via props; this module owns every user-facing string.

/** Hero section */
export const heroContent = {
  eyebrow: 'LIVE AI LAB',
  title: '从代码开始，探索 AI 世界',
  description:
    '课程学习、在线编程、Notebook、自动判题、考试与 AI 评分，在一个持续运转的学习工作台里完整呈现。',
  primaryAction: '探索平台能力',
  secondaryAction: '立即登录',
}

/** Code window demo — 10-line Python training example */
export const codeLines = [
  { text: 'import torch', indent: 0 },
  { text: 'import torch.nn as nn', indent: 0 },
  { text: '', indent: 0 },
  { text: 'model = nn.Sequential(', indent: 0 },
  { text: 'nn.Linear(784, 256),', indent: 1 },
  { text: 'nn.ReLU(),', indent: 1 },
  { text: 'nn.Linear(256, 128),', indent: 1 },
  { text: 'nn.ReLU(),', indent: 1 },
  { text: 'nn.Linear(128, 10)', indent: 1 },
  { text: ')', indent: 0 },
]

export const codeOutput = {
  status: 'completed',
  epochs: '20/20',
  accuracy: '98.6%',
  testsPassed: true,
  score: 95,
  scoreLabel: 'AI 评分',
  scoreComment: '代码结构清晰，测试覆盖完整',
}

/** Navigation */
export const navLinks = [
  { id: 'capabilities', label: '平台能力' },
  { id: 'learning-loop', label: '学习闭环' },
  { id: 'roles', label: '角色场景' },
]

/** Capability gallery — 8 distinct platform capabilities */
export const capabilities = [
  {
    id: 'courses',
    icon: 'courses',
    title: '课程学习',
    summary: '结构化 Python 课程体系，从基础语法到深度学习，循序渐进。',
    tags: ['视频讲解', '交互式示例', '分阶段评测'],
  },
  {
    id: 'coding',
    icon: 'coding',
    title: '在线编程',
    summary: '浏览器内直接编写与运行 Python 代码，零环境配置，打开即用。',
    tags: ['内置 Python 3', '自动保存', '多文件支持'],
  },
  {
    id: 'notebook',
    icon: 'notebook',
    title: 'Notebook 实验',
    summary: '交互式 Jupyter Notebook，边写边看，像科学家一样探索数据。',
    tags: ['富文本输出', '图表可视化', '逐步执行'],
  },
  {
    id: 'assignments',
    icon: 'assignments',
    title: '作业管理',
    summary: '布置、提交、批改全流程在线化，支持截止时间和自动提醒。',
    tags: ['批量发布', '截止管理', '提交记录'],
  },
  {
    id: 'exams',
    icon: 'exams',
    title: '在线考试',
    summary: '限时编程考试，防作弊检测，自动收卷与即刻出分。',
    tags: ['限时模式', '题目随机', '自动收卷'],
  },
  {
    id: 'judging',
    icon: 'judging',
    title: '自动判题',
    summary: '多组用例秒级评测，精确错误定位，通过/失败一目了然。',
    tags: ['多组用例', '错误定位', '性能评测'],
  },
  {
    id: 'ai-grading',
    icon: 'aiGrading',
    title: 'AI 评分',
    summary: '大模型驱动的代码评审，从正确性、风格、效率多维度给出反馈。',
    tags: ['代码风格', '复杂度分析', '改进建议'],
  },
  {
    id: 'templates',
    icon: 'templates',
    title: '实验模板',
    summary: '预置常见 Python 实验场景模板，快速启动教学与练习。',
    tags: ['一键创建', '场景分类', '可定制'],
  },
]

/** Learning loop — 5-step continuous cycle */
export const learningSteps = [
  {
    n: '01',
    title: '学习',
    desc: '进入结构化课程与 Notebook，跟随交互式示例逐步建立 Python 知识体系。',
  },
  {
    n: '02',
    title: '实验',
    desc: '在浏览器中直接编写代码，实时运行验证，边学边练加深理解。',
  },
  {
    n: '03',
    title: '提交',
    desc: '作业或考试提交后，系统自动运行多组测试用例，秒级返回结果。',
  },
  {
    n: '04',
    title: '评测',
    desc: '全部测试通过，结合代码质量，大模型给出分数、评语和改进建议。',
  },
  {
    n: '05',
    title: '进步',
    desc: '查看反馈详情、能力雷达、练习记录，把每一次提交都变成可见的成长。',
  },
]

/** Role scenes — four user perspectives */
export const roles = [
  {
    id: 'student',
    title: '学生',
    subtitle: 'Learning Journey',
    desc: '随时随地学习编程，在线练习、自动判题、AI 反馈，让每一次练习都有收获。',
    highlights: ['结构化课程', '在线编程', '自动判题', 'AI 反馈'],
  },
  {
    id: 'teacher',
    title: '教师',
    subtitle: 'Teaching Dashboard',
    desc: '发布课程、布置作业、组织考试，全班学习数据一览无余。',
    highlights: ['课程管理', '作业批改', '成绩分析', '教学洞察'],
  },
  {
    id: 'admin',
    title: '管理员',
    subtitle: 'Platform Control',
    desc: '用户管理、权限配置、系统监控，保障平台安全稳定运行。',
    highlights: ['用户管理', '权限控制', '系统监控', '数据报表'],
  },
  {
    id: 'developer',
    title: '开发者',
    subtitle: 'Extend & Integrate',
    desc: '开放 API、判题沙箱、插件扩展，构建你的定制化教学工具链。',
    highlights: ['开放 API', '判题沙箱', '插件系统', '自定义模板'],
  },
]

/** Final CTA */
export const finalCta = {
  title: '准备好开始了吗？',
  description: '免费注册，即刻体验完整的 Python 在线学习与实验平台。',
  action: '立即登录',
}
