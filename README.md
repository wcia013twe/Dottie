# Dottie — Interactive Braille Learning Companion

**Making Braille literacy more accessible through computer vision, tactile interaction, and adaptive learning.**

Dottie is an assistive learning prototype that connects everyday objects with Braille literacy. Using a camera, object recognition, spoken guidance, and a custom six-dot Braille cell, Dottie explores how children can learn Braille through their environment rather than relying exclusively on traditional letter drills.

The project also explores a data-driven learning architecture using Databricks to support personalized activities, track learning progress, and ground educational guidance in research.

## The Problem

According to the National Braille Press, only 10% of blind schoolchildren receive Braille instruction.

Braille literacy can support independence, communication, and educational development, but access to specialized equipment and instructional resources remains limited.

We wanted to explore a different approach: **What if learning Braille felt more like discovering the world than memorizing an alphabet?**

Dottie connects physical objects, tactile characters, and interactive storytelling to create opportunities for meaningful practice.

## Features

### 1. Object Recognition & Exploration

An external camera observes the child's surroundings and identifies recognizable objects using computer vision.

A pointing interaction allows learners to select detected objects, which are then translated into text and corresponding Braille patterns.

- Real-time object detection using YOLO
- Object selection through spatial pointing
- Text-to-Braille translation
- Spoken feedback for object identification

### 2. Six-Dot Braille Cell

We designed and fabricated a mechanical Braille cell prototype using six individually controlled servo motors.

Each servo corresponds to one dot in the standard 2 × 3 Braille configuration.

The design explores an inexpensive, reproducible alternative to specialized refreshable Braille hardware.

**Hardware components:**

| Component | Purpose |
|---|---|
| NVIDIA Jetson Nano | Edge inference and object recognition |
| External camera | Captures the surrounding environment |
| Arduino Uno | Braille cell control |
| 6 × SG90 servos | Mechanical actuation of Braille dots |
| 3D-printed components | Braille housing and actuation mechanisms |
| External power supply | Supplies power to the servos |

### 3. Interactive Storytelling

Dottie extends beyond individual letters by placing Braille practice into everyday learning experiences.

The companion application explores contextual activities that connect recognized objects with words, stories, and spoken instructions.

For example, identifying a household object can introduce its spelling, Braille representation, and a related learning activity.

### 4. Adaptive Learning Architecture

We designed a Databricks-based architecture to explore how learner activity could inform personalized instruction.

The proposed system separates raw interaction data, structured learning observations, and research-backed teaching recommendations.

Potential capabilities include:

- Tracking practice history and recurring difficulties
- Building learner profiles from interaction events
- Retrieving relevant educational research
- Generating personalized activity recommendations
- Evaluating AI-generated instructional guidance

This design draws inspiration from research on Databricks and Delta-based architectures for analyzing learner behavior and supporting personalized learning ([Nguyen et al., 2025](https://doi.org/10.5220/0013202900003932)).

## System Architecture

Dottie combines three major subsystems: perception, tactile interaction, and personalized instruction.

### Computer Vision & Hardware

```text
External Camera
      |
      v
Jetson Nano
  |-- YOLO Object Detection
  |-- Pointing / Object Selection
  |-- Label Recognition
  |-- Text-to-Braille Translation
      |
      v
Python Application
  |-- Spoken Guidance
  |-- Learning Interface
  |-- Braille Pattern Output
      |
      v
Arduino Uno
      |
      v
Six-Servo Braille Cell
```

The Jetson Nano handles object recognition and translation logic, while the Arduino handles low-level actuator control.

This separation allows the perception and learning software to evolve independently from the mechanical Braille cell.

### Proposed Learning Intelligence Pipeline

```text
Local Learning Application
(HTML / CSS / JS + Python Bridge)
             |
             v
Databricks AI Services
(Apps / LangGraph / Model Serving)
             |
             v
Unity Catalog + Delta Lake
  |
  |-- Bronze: Raw Events & Documents
  |-- Silver: Learning Observations
  |-- Gold: Profiles & Approved Guidance
             |
             v
Research Retrieval
(PDFs -> Volumes -> AI Functions
 -> Delta -> AI Search)
             |
             v
Evidence-Grounded Activities
& Personalized Recommendations
```

**Data processing**

The proposed medallion architecture organizes learner interactions and educational research into progressively refined data layers.

**Research retrieval**

Research documents can be processed into searchable passages, allowing instructional recommendations to reference supporting educational evidence.

**Model evaluation**

An MLflow-based workflow was also designed for tracing, prompt evaluation, and candidate/champion prompt management, with GEPA explored as a possible optimization strategy.

These Databricks components represent the intended learning intelligence architecture rather than a claim that every service was deployed during the hackathon.

## Technology Stack

| Layer | Technologies |
|---|---|
| Computer vision | Python, YOLO |
| Edge computing | NVIDIA Jetson Nano |
| Embedded systems | Arduino, C/C++, servo control |
| Hardware design | CAD, 3D printing |
| Web companion | HTML, CSS, JavaScript |
| Data architecture | Databricks, Delta Lake, Unity Catalog |
| AI orchestration (proposed) | LangGraph, Model Serving |
| Retrieval (proposed) | Databricks AI Search |
| Evaluation (proposed) | MLflow, GEPA |

## Engineering Challenges

### Mechanical Design

Our team had limited prior experience with CAD and 3D printing.

Building a compact six-dot Braille mechanism required translating digital models into physical moving parts while accounting for clearances, tolerances, and actuator movement.

We iterated on the mechanical design to explore how six independent actuators could fit into a small tactile interface.

### Power Distribution

Controlling six servos introduced electrical challenges involving current draw, voltage regulation, and shared power distribution.

We explored how to power multiple motors without exceeding the Arduino's power capabilities.

Reliable simultaneous actuation remained an unresolved hardware integration challenge during the hackathon.

### System Integration

The project spans several engineering domains:

- Computer vision and object localization
- Embedded actuator control
- Mechanical prototyping
- Web application development
- Data engineering and AI orchestration

Developing these subsystems in parallel made integration and debugging a major challenge.

### Personalized Learning

Designing useful adaptive instruction requires more than generating educational content.

We explored how learner observations could be connected to research evidence and evaluated recommendations, while keeping the learning application independent of the underlying data infrastructure.

## Project Status

**Hackathon prototype — proof of concept**

| Component | Status |
|---|---|
| Object recognition pipeline | Implemented |
| Text-to-Braille translation | Implemented |
| Web learning companion | Prototype |
| Six-dot CAD design | Completed |
| Arduino servo firmware | Developed |
| Physical Braille mechanism | Fabricated prototype |
| Reliable tactile actuation | Not yet achieved |
| Databricks learning architecture | Designed / explored |
| End-to-end adaptive instruction | Future work |

The software prototype demonstrates the intended learning interaction. The physical Braille cell was fabricated, but the team did not achieve a fully operational, integrated tactile display within the hackathon.

## Future Development

### Hardware
- Improve mechanical reliability and dot actuation.
- Refine the enclosure and reduce overall size.
- Validate tactile dimensions and usability with Braille educators and readers.

### Learning Experience
- Expand interactive storytelling activities.
- Add structured learning progression and practice sessions.
- Improve accessibility and nonvisual navigation.

### Learning Intelligence
- Implement persistent learner profiles.
- Ingest and index relevant educational research.
- Build evidence-grounded activity recommendations.
- Evaluate personalized instruction using reproducible test cases and model traces.

## What We Learned

Dottie challenged us to work across unfamiliar disciplines within a limited development window.

The most valuable lesson was the difference between implementing individual subsystems and producing a reliable integrated device.

We developed a working computer vision and Braille translation pipeline, explored embedded actuation, and built a physical prototype while learning how hardware constraints shape software decisions.

More importantly, the project demonstrated how computer vision and tactile interaction could be combined into a more engaging approach to Braille education.

## Research & Acknowledgments

- [National Braille Press](https://www.nbp.org/) — Braille literacy advocacy and educational resources.
- [Nguyen et al. (2025)](https://doi.org/10.5220/0013202900003932) — Research inspiration for learner analytics and personalized learning using Databricks and Delta architecture.

---

*Dottie is an exploratory educational technology project developed during a hackathon. It is not a validated assistive device or a replacement for professional Braille instruction.*
