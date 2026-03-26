# Skill Evaluation Rubric

Evaluation criteria for SKILL.md quality. Scores use a 1–50 scale for fine-grained discrimination.

## Scoring Dimensions

Each dimension is scored 1–50 with the given weight. Use the FULL range. A score of 25 is average. A score of 40+ requires excellence across all indicators.

### 1. Structural Completeness (weight: 1.0)

Does the skill have all necessary sections for a design skill?

- 1–10: Missing critical sections (no phases, no examples)
- 11–20: Has main sections but missing important subsections
- 21–30: Most sections present but some lack depth
- 31–35: All required sections present with adequate detail
- 36–40: All sections present, well-organized, good depth
- 41–45: Comprehensive coverage, logical flow between sections
- 46–50: Every section maximally useful, perfect organization, no gaps

Required elements (check each):
- Frontmatter (name, description)
- Usage section with invocation syntax
- Description section explaining deliverables
- Instructions with clearly defined phases
- Guidelines section with design principles
- Complete worked example covering all phases
- Implementation protocol for executing designs

Score 35+ requires ALL elements present. Score 40+ requires each element to be well-developed. Score 45+ requires elements to reinforce each other.

### 2. Instruction Clarity (weight: 1.5)

Are instructions unambiguous and actionable?

- 1–10: Vague, open to wide interpretation
- 11–20: Generally clear but many steps require guessing
- 21–30: Most steps clear, some decision points ambiguous
- 31–35: Clear instructions with specific actions for most steps
- 36–38: Clear actions, most decision points have criteria, most phases have completion signals
- 39–41: All steps have clear actions, all decision points have criteria, explicit phase transitions
- 42–44: Every step unambiguous with success criteria, agent always knows when to ask vs. proceed
- 45–47: Perfect clarity — no step requires interpretation, every transition is triggered
- 48–50: Ideal reference quality — could serve as a template for other skills

Indicators (each adds ~2 points when present):
- Each numbered step has a clear action verb
- Success/completion criteria stated for each phase
- Decision points have explicit criteria (not "as appropriate")
- Agent knows when to ask the user vs. proceed autonomously
- Transitions between phases have clear triggers

### 3. Actionability (weight: 1.5)

Can an agent execute each step without external guidance?

- 1–10: Steps require significant interpretation
- 11–20: Some steps actionable, many need context
- 21–30: Most steps executable, output format unclear
- 31–35: All steps executable with clear inputs/outputs
- 36–38: Steps specify tools for most operations
- 39–41: Steps specify tools AND output formats for deliverables
- 42–44: Every step has tools, formats, and produces a named artifact
- 45–47: Agent knows exactly what to present, when to wait, what format to use
- 48–50: No external guidance needed — skill is a complete execution manual

Indicators (each adds ~2 points when present):
- Steps specify what tools to use (Glob, Grep, Read, Agent, etc.)
- Output format is defined for each deliverable
- Each phase produces a named artifact
- Agent knows what to present to the user and when to wait for feedback

### 4. Example Quality (weight: 1.0)

Does the example demonstrate the full workflow?

- 1–10: No example or trivial/incomplete
- 11–20: Partial example, some phases shown
- 21–30: Most phases shown with basic content
- 31–35: Full example covering all phases with realistic content
- 36–38: Full example with realistic PRD and task content, shows user interaction
- 39–41: Demonstrates decision-making (why choices were made), shows trade-offs
- 42–44: Shows agent reasoning, grounded decisions with specific file references
- 45–47: Demonstrates edge cases, shows how the agent discovers and reasons about patterns
- 48–50: Could be used as a training example — shows complete thinking process

Quality markers (each adds ~2 points):
- Example walks through every phase
- Shows realistic PRD content (not placeholders)
- Shows realistic task list with test-first ordering
- Demonstrates decision-making (why choices were made)
- Shows user interaction points
- Shows agent reasoning connecting exploration findings to design decisions

### 5. Conciseness (weight: 0.5)

Is the skill as concise as possible while maintaining completeness?

- 1–10: Extremely verbose with major redundancy, OR so terse it's unusable
- 11–20: Significant redundancy or wordiness
- 21–30: Some redundancy that could be trimmed
- 31–35: Well-balanced, minimal redundancy
- 36–38: Every section earns its place, minimal filler
- 39–41: Tight writing, no redundancy between sections
- 42–44: Removing any sentence would lose information
- 45–47: Maximally dense — every word carries meaning
- 48–50: Impossible to shorten without losing value

Red flags (each subtracts ~3 points):
- Same instruction repeated in different sections
- Lengthy explanations where a concise rule suffices
- Filler phrases that add no information
- Excessive formatting that obscures content

### 6. Adaptability (weight: 1.0)

Does the skill handle different feature sizes and contexts?

- 1–10: Only works for one type of feature
- 11–20: Handles common cases only
- 21–30: Handles small, medium, large but no edge cases
- 31–35: Explicit guidance for small, medium, and large features
- 36–38: Handles size variations with decision rules, some adaptive behavior
- 39–41: Clear decision rules for all sizes, phases adapt based on scope
- 42–44: Handles all sizes, ambiguous scope, novel patterns, unfamiliar codebases
- 45–47: Every scenario has explicit handling, adaptive phase depth, graceful fallbacks
- 48–50: Handles any conceivable design scenario with clear guidance

Scenarios to consider (each adds ~3 points when handled):
- Single-file feature (should skip PRD)
- Multi-subsystem feature (should consider splitting)
- Ambiguous feature request (should ask clarifying questions)
- Feature that introduces new patterns (should flag for review)
- Feature in an unfamiliar codebase (should explore thoroughly)

### 7. Test-First Fidelity (weight: 1.0)

Is the test-first approach properly embedded throughout?

- 1–10: Tests mentioned but not integral
- 11–20: Tests included but not consistently first
- 21–30: Tests come first in task ordering
- 31–35: Test-first in task ordering and acceptance criteria
- 36–38: Test-first woven through criteria, tasks, and implementation protocol
- 39–41: Tests drive acceptance criteria (criteria ARE test specs), tasks always start with tests
- 42–44: Implementation protocol enforces test-first, explicitly prevents untested code
- 45–47: Tests are the specification — the entire design flows from test definitions
- 48–50: Perfect test-first discipline — impossible to use the skill without writing tests first

### 8. Grounding (weight: 1.0)

Does the skill ensure designs are grounded in the actual codebase?

- 1–10: No mention of codebase exploration
- 11–20: Mentions exploring but no specifics
- 21–30: Some specific exploration instructions
- 31–35: Specific instructions for what to explore, decisions should reference findings
- 36–38: Exploration uses specific tools, most decisions tied to patterns
- 39–41: Every decision must cite codebase patterns, parallel exploration with tools
- 42–44: Explicit fallback for novel patterns, exploration protocol with specific tool calls
- 45–47: Every decision grounded, example demonstrates grounded reasoning, novel pattern handling shown
- 48–50: Perfect grounding — impossible to make an ungrounded decision following this skill

## Composite Score Calculation

```
weighted_sum = (structural * 1.0) + (clarity * 1.5) + (actionability * 1.5) +
               (example * 1.0) + (conciseness * 0.5) + (adaptability * 1.0) +
               (test_first * 1.0) + (grounding * 1.0)

max_possible = 425.0  # all dimensions at 50 with their weights

quality_score = weighted_sum / max_possible * 10
```

## Required Output Format

The evaluator must output scores in this exact format:

```
structural_completeness:  N
instruction_clarity:      N
actionability:            N
example_quality:          N
conciseness:              N
adaptability:             N
test_first_fidelity:      N
grounding:                N
```

Where N is an integer from 1 to 50.
