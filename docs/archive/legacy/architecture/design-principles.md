Introduction

Agentic AI systems represent a significant evolution — moving beyond the capabilities of standalone large language models (LLMs) to create intelligent systems that can reason, plan, and interact with the world through tools. These systems combine the reasoning power of LLMs with specialized tools that enable them to perform concrete actions.

The emergence of agentic AI systems addresses fundamental limitations of traditional AI approaches:

1. Bridging Reasoning and Action: While LLMs excel at reasoning, language understanding, and generation, they cannot directly interact with external systems. Agentic AI bridges this gap by pairing LLMs with purpose-built tools that extend their capabilities into the physical and digital worlds.

2. Architectural Clarity for Complex Tasks: As AI systems tackle increasingly complex workflows, ad-hoc architectures become untenable. A principled approach to agent design enables systems that remain maintainable and reliable even as their capabilities grow.

3. Specialization and Collaboration: Just as human organizations benefit from specialized roles and clear responsibilities, agentic AI systems can achieve similar benefits through well-defined agent roles, tool boundaries, and task structures.

This guide provides a comprehensive framework for designing effective agentic systems, with practical recommendations based on real-world implementations. The core insight driving these recommendations is that establishing clear boundaries between agents (decision-makers), tools (executors), and tasks (unit work) creates systems that are more maintainable, testable, and ultimately more effective at solving complex problems.

Whether you’re building a document processing pipeline, a code generation system, an AI assistant, or any other complex AI application, these principles will help you create robust architectures that can evolve and scale to meet changing requirements.

1. Design Principles
1.1 Agent Design Principles

Single Responsibility: Each agent should have clear, focused responsibilities. Just as in software development, this principle ensures agents remain specialized and maintainable.
Explicit Reasoning: Agents should explain their decision-making process, making their thought patterns transparent and debuggable.
Clear Interfaces: Well-defined input/output contracts ensure agents interact properly with tools and other agents.
Separation of Concerns: Maintain a strict boundary between detection (what exists) and interpretation (what it means).
Task Independence: Design tasks that can be executed and reasoned about independently to create modular, maintainable systems.
1.2 Task Design Principles

Purpose: Tasks define what needs to be done and how to approach it. They serve as the units of work in an agentic system.

Characteristics:

Defined with clear descriptions (for example, YAML configuration in crewAI implementation)
Provide instructions that guide agent thinking
Specify expected outputs
Can depend on other tasks
Provide context from previous tasks
1.3 Tool Design Principles

Purpose: Tools perform specific, well-defined technical operations. They are the system’s means of interacting with data and the external world.

Characteristics:

Focus on deterministic functionality
Encapsulate technical operations (e.g., Git operations, file analysis)
Return structured data but avoid making decisions
Should be reusable across different tasks
Best Practices for Tool Design:

Single Responsibility Principle: Each tool does one thing well
Clear Input/Output Contracts: Define explicit models for inputs and outputs
Domain-Specific Logic: Complex algorithms belong in tools
Refactor Complex Methods: Break down into smaller, focused methods
eep Business Rules: Domain-specific rules should be in tools

2. Agentic System Architectures
A typical Agentic system architecture would be as follows:
https://miro.medium.com/v2/resize:fit:4800/format:webp/1*tZxXEOynqcVfMN6Ln3ASHg.png

When developing an application using AI Agentic, implement a clear orchestration flow where specialized agents handle different aspects of the task:

Strategic Agents: Define high-level approaches, make key decisions, and determine the overall plan.
Validation Agents: Verify outputs against quality standards, requirements, or constraints.
Refinement Agents: Make improvements or corrections based on validation feedback or identified issues.
Agents should explain their reasoning and decisions at each step to provide transparency, enable debugging, and build user trust.

Clear Boundaries: Tools vs. Agents

The most common and critical design challenge in agentic systems is failing to establish clear boundaries between agent responsibilities and tool functionalities. Getting this right is key to building robust, maintainable, and effective systems.

Tools Should:

Perform specific, well-defined operations with clear inputs and outputs (e.g., API calls, data transformations, calculations, specific pattern detection).
Encapsulate technical logic, complex algorithms, and domain-specific deterministic operations.
Ideally remain stateless and reusable across different tasks or agents.
Return structured, predictable, and well-typed data for agents to reliably reason about.
Focus on the “what” — executing actions or detecting objective facts and patterns.
Agents Should:

Make strategic decisions about which tools to use, in what sequence, and how to interpret their outputs.
Interpret results, form judgments, and handle ambiguity based on tool outputs and task context.
Maintain the context of the overall task state, progress, and objectives.
Handle nuances, incomplete information, and apply heuristics or learned strategies.
Manage user interactions, explanations, and potentially ask clarifying questions.
Focus on the “so what” — interpreting patterns, weighing options, and deciding on subsequent actions or final conclusions.
Key Decision Rule: When unsure where functionality belongs, ask: “Is this recognizing what objectively exists (or executing a defined action), or is it deciding what should be done about it (interpreting, strategizing)?” Detection and execution belong in tools; interpretation and decision-making belong with agents.

3. Task-Driven Architecture
I introduce an approach that I call “Task-Drive Architecture”, which is a way to structure your system around well-defined tasks rather than direct agent-to-agent method calls:

Agents define who (roles, responsibilities, high-level objectives).
Tasks define what (specific actions, sub-goals, required outputs). Task Context provides instructions on how to approach problems (data, constraints, user preferences).
Tools provide the means to execute specific operations needed within a task.
This creates a clearer workflow where orchestration happens through assigning and completing tasks, making the system easier to manage and modify.

Boundaries Between Agents, Tasks, and Tools

https://miro.medium.com/v2/resize:fit:4800/format:webp/1*zbvE3OM1YtQqeCGNLXHNNw.png

What Tools Should Do:

1.Perform Specific, Well-Defined Operations: Tools should focus on executing concrete operations with clear inputs and outputs.

2. Encapsulate Technical Logic: Complex algorithms, data processing, and domain-specific operations belong in tools.

3. Be Stateless and Reusable: Tools should be designed to be called multiple times with different inputs.

4. Return Structured Data: Tools should return well-typed, structured data that agents can reason about.

What Agents Should Do:

1. Make Strategic Decisions: Deciding which tools to use and in what order.

2. Interpret Results: Understanding the meaning of tool outputs and making judgments.

3. Maintain Context: Keeping track of the overall task state and progress.

4. Handle Ambiguity: Dealing with unclear or incomplete information that requires judgment.

5. Interact with Users: Managing the dialogue and explaining what’s happening.

4. Decision Framework for Tool vs. Agent Responsibilities

Tools for Deterministic, Rule-Based Tasks: Implement tasks with clearly defined inputs and outputs as tools. These include operations like parsing repositories, computing diffs, aggregating file metadata, performing directory analysis, and executing grouping algorithms based on strict criteria.

Agents for Higher-Level Reasoning: Reserve agent logic for tasks requiring subjectivity, pattern recognition, and nuanced judgment. For example, deciding on the best grouping strategy, validating the coherence of PR groups, generating titles and descriptions, or providing a rationale for grouping decisions.

4. Trade-offs and Considerations in Agentic System Design
When designing agentic AI systems, several important trade-offs must be considered. Understanding these trade-offs helps developers make informed decisions that align with their specific requirements.

Modularity vs. Performance
Trade-off: Highly modular systems with many small tools offer better maintainability but may introduce performance overhead due to increased context switching and potentially more LLM calls.

Considerations:

For performance-critical applications, batch related operations into logical units
Use async processing where possible for independent operations
Consider caching tool results for frequently accessed data
For complex workflows, the maintainability benefits of modularity often outweigh performance costs
Agent Complexity vs. Tool Logic
Trade-off: Placing more logic in agents (via prompting) reduces code complexity but may decrease determinism and testability.

Considerations:

Critical operations that must be deterministic should always be tools
If an operation might change in response to user needs, agent-based implementation offers more flexibility
Consider hybrid approaches where agents determine parameters for deterministic tools
Document the rationale for design decisions to clarify intent
Specialization vs. Flexibility
Trade-off: Highly specialized agents are more effective at specific tasks but less adaptable to changing requirements.

