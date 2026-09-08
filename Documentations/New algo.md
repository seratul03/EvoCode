```
┌─────────────────────────────────────────────────────────────────┐
│                      AIECG Main Loop                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                ┌─────────────┼─────────────┐
                │             │             │
         Generation        Fitness        Selection 
                │             │             │
                ↓             ↓             ↓
        ┌──────────────────────────────────────────┐
        │  Compute Multi-Objective Fitness         │
        │  - Correctness, Runtime, Complexity      │
        │  - Behavioral Novelty (#7, #8)           │
        │  - Failure diagnosis (#6)                │
        └──────────────────────────────────────────┘
                              │
                ┌─────────────┼──────────────────┐
                │             │                  │
           Adaptive     Learning-to-Mutate    RL Agent
              (#1)           (#2)              (#3)
                │             │                  │
                ↓             ↓                  ↓
          ┌──────────────────────────────────────────┐
          │  Mutation Strategy Selection             │
          │  - RL agent recommends strategy (#3)     │
          │  - Learned mutation effectiveness (#2)   │
          │  - Adaptive rates (#1)                   │
          └──────────────────────────────────────────┘
                              │
                ┌─────────────┼─────────────┐
                │             │             │
              Mutator        Critic      Validator
              Evolves        Evolves      Evolves
              (#4)            (#4)         (#4)
                │              │             │
                ↓              ↓             ↓
         ┌──────────────────────────────────────────┐
         │  Apply Mutations (Co-evolved agents)     │
         │  + Failure-driven targeting (#6)         │
         └──────────────────────────────────────────┘
                              │
        ┌─────────────────────┼──────────────────────┐
        │                     │                      │
       Stuck? (#9)  → Query LLM Memory (#5)  Population of
                                            Strategies (#10)
        │                     │                      │
        ↓                     ↓                      ↓
   Landscape              Transfer Learning     Strategy
   Detection              + Mutation Bias       Competition
   (#9)                   (#5)                  (#10)
        │                     │                      │
        └─────────────────────┼──────────────────────┘
                              │
                ┌─────────────┴─────────────┐
                │                           │
                ↓                           ↓
        ┌─────────────────────┐  ┌────────────────────┐
        │  Selection via      │  │  Store Memory      │
        │  - Behavioral       │  │  - Success logs    │
        │    Diversity (#7)   │  │  - Failure logs    │
        │  - Novelty (#8)     │  │  - Mutations       │
        │  - Multi-objective  │  │  - Strategy perf   │
        │    clustering       │  │  (#5)              │
        └─────────────────────┘  └────────────────────┘
                │                           │
                └─────────────┬─────────────┘
                              │
                        Next Generation
```