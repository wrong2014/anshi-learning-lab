# P01 研究支持的理科学习卡点因子框架 v02

日期：2026-06-27

## 设计目标

P01 不做心理诊断，也不替代教师诊断。它要做的是：通过家长和孩子对“最近一次真实卡住事件”的自然描述，尽量稳定地定位最可能优先影响学习的学习过程因子，并给出 7 天内可执行的家庭支持动作。

## 研究依据对应

### 1. 学习不是单点能力，而是多个环节协同

学习科学通常把理解、迁移、先验知识、元认知和情境支持看成相互作用的系统。P01 因此不把“学不好”归为单一原因，而是用主因 + 次因的方式呈现。

对应因子：

- 前置知识缺口
- 概念理解不稳
- 建模与迁移困难
- 元认知与复盘薄弱
- 家庭支持与 AI 使用失位

参考：

- National Academies, *How People Learn II: Learners, Contexts, and Cultures*
- National Research Council, *How Students Learn: History, Mathematics, and Science in the Classroom*

### 2. 数学和理科问题解决至少包含“理解、表征、策略、执行、反思”

数学能力不只是计算。经典数学学习框架强调概念理解、程序流畅、策略能力、自适应推理和积极倾向。理科问题解决也高度依赖把文字、图像、符号、方程式、过程图互相转换。

对应因子：

- 学科语言与符号理解困难
- 表征转换困难
- 建模与迁移困难
- 程序执行不稳定
- 情绪动机与自我效能受损

参考：

- National Research Council, *Adding It Up: Helping Children Learn Mathematics*
- Institute of Education Sciences, *Improving Mathematical Problem Solving in Grades 4 Through 8*

### 3. “看懂答案”不等于真正掌握

教育心理学关于学习策略的研究通常支持检索练习、间隔练习、错题后的延迟复测，而不是只重读、只看答案、只划重点。P01 因此把“看答案懂、下次不会”单独作为学习策略和元认知证据。

对应因子：

- 元认知与复盘薄弱
- 学习策略低效
- 程序执行不稳定

参考：

- Dunlosky et al. (2013), *Improving Students' Learning With Effective Learning Techniques*

### 4. 青少年不是“小版成人”：情绪、自我效能和家庭互动会影响启动

初二升初三阶段的孩子，理科学习压力、同伴比较、考试临近、亲子互动方式都会影响启动和坚持。P01 不把烦躁、回避、抗拒直接解释成“态度差”，而是作为学习启动和支持方式是否错位的信号。

对应因子：

- 情绪动机与自我效能受损
- 家庭支持与 AI 使用失位
- 注意与工作记忆负荷过高

参考：

- Bandura, self-efficacy research
- National Academies, *How People Learn II*

### 5. 错误概念不是“没记住”，而是孩子带着一套错误解释系统在推理

物理、化学中常见的“直觉经验”会让孩子非常自信地走向错误，例如力和运动、电流、守恒、化合价、微粒变化等。P01 因此新增“错误概念/朴素经验干扰”，用于区分“不会启动”和“带着错误规则启动”。

对应因子：

- 错误概念或朴素经验干扰
- 概念理解不稳
- 表征转换困难

参考：

- National Research Council, *Taking Science to School*
- National Research Council, *How Students Learn*

## v02 内部因子集合

| 因子 | 典型信号 | 关键追问 |
|---|---|---|
| 前置知识缺口 | 新内容一学就散，追到旧知识卡住 | 这题是不是要用到上一单元/上学期内容？ |
| 概念理解不稳 | 会背公式定义，但讲不清含义 | 能不能不用课本话解释？ |
| 错误概念或朴素经验干扰 | 孩子很笃定，但规则本身错 | 他当时是怎么解释自己做法的？ |
| 学科语言与符号理解困难 | 题干条件、符号、单位读错 | 哪个词、符号、条件最不确定？ |
| 表征转换困难 | 文字转不成图、图转不成式 | 能不能先画图/列关系？ |
| 建模与迁移困难 | 例题会，变式不会启动 | 他怎么决定用哪个方法？ |
| 程序执行不稳定 | 步骤、计算、单位、检查总漏 | 错在想法还是执行流程？ |
| 注意与工作记忆负荷过高 | 条件一多就乱、丢条件 | 如果拆成三小步，哪一步先乱？ |
| 元认知与复盘薄弱 | 说不清从哪一步不会 | 孩子能不能指出第一处断点？ |
| 学习策略低效 | 看答案懂，隔天不会 | 错题后有没有隔天独立重做？ |
| 情绪动机与自我效能受损 | 烦、急、逃、怕错 | 是先不会，还是先紧张/抗拒？ |
| 家庭支持与 AI 使用失位 | 父母/AI 很快给完整答案 | 帮助是在追问，还是接管思路？ |

## 对话策略

- 第一轮只让用户说，不给场景选项。
- 如果用户已经自然提供学科，不再问学科。
- 如果用户描述中可能并存多个因素，用多选降低输入成本。
- “都不像/其他”必须展开自由输入，不直接提交选项。
- 每轮最多只追一个方向：卡住步骤、错因模式、家庭支持、错后处理、情绪/AI 使用。
- 信息够用时直接出结果，不为了完整问卷而继续追问。

## 参考链接

- https://nap.nationalacademies.org/catalog/24783/how-people-learn-ii-learners-contexts-and-cultures
- https://nap.nationalacademies.org/catalog/10126/how-students-learn-history-mathematics-and-science-in-the-classroom
- https://nap.nationalacademies.org/catalog/9822/adding-it-up-helping-children-learn-mathematics
- https://ies.ed.gov/ncee/wwc/PracticeGuide/16
- https://journals.sagepub.com/doi/10.1177/1529100612453266
- https://nap.nationalacademies.org/catalog/11625/taking-science-to-school-learning-and-teaching-science-in-grades
