# Agentic Portal Experimental

An experimental design sandbox for the Agentic Portal, featuring an animated agent infrastructure visualization.

## Features

- **Animated Agent Network Background**: Interactive visualization of the 3-tier agent architecture
- **Flow Visualization**: Watch data flow between agents with animated particles
- **Dark Cyberpunk Aesthetic**: Inspired by system monitoring interfaces
- **Marketing-Ready Design**: Fun, visual representation of the agent infrastructure

## Getting Started

```bash
# Install dependencies
npm install

# Run development server (port 3001 to avoid conflict with main portal)
npm run dev
```

Open [http://localhost:3001](http://localhost:3001) to view the experimental portal.

## Structure

```
src/
├── app/
│   ├── page.tsx          # Landing page with agent visualization
│   ├── dashboard/        # Demo dashboard
│   └── layout.tsx        # Root layout
├── components/
│   └── agent-network-background.tsx  # Animated agent network
└── lib/
    └── utils.ts          # Utilities
```

## Design Notes

This is a **design sandbox** separate from the production portal. Use it to:

- Experiment with new UI/UX ideas
- Test animations and interactions
- Create marketing materials
- Prototype new features

Changes here do NOT affect the main portal at `apps/portal`.
