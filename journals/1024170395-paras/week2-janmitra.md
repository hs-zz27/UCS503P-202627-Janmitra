# Janmitra — Weekly Engineering Journal

## Week 2 — Frontend Planning, Interface Design and Repository Setup

| Field                 | Value                                                                                                                                                                                                                                               |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Course                | UCS503 / UCS503P — Software Engineering                                                                                                                                                                                                             |
| Institute             | Thapar Institute of Engineering and Technology, Patiala                                                                                                                                                                                             |
| Project               | Janmitra — a voice-first civic scheme guidance platform                                                                                                                                                                                             |
| Week                  | 11 – 17 August 2026                                                                                                                                                                                                                                 |
| Member                | Paras (1024170395)                                                                                                                                                                                                                                  |
| Status at end of week | Project scope and architecture were finalised with the team. The frontend direction was planned around a browser-based voice-call harness using Next.js and LiveKit, with the initial frontend structure and component responsibilities identified. |

---

## 1. Objective for the week

The main objective this week was to finalise the project scope with the team and define how the frontend would provide a simple interface for interacting with the Janmitra voice assistant.

Since Janmitra is primarily a voice-first system, the frontend was planned as a browser-based development and testing harness rather than the final citizen-facing channel. The interface needed to keep the interaction simple, with clear call controls, connection status and feedback about the current voice session.

The frontend direction was planned around Next.js and LiveKit, while keeping the frontend independent from the core eligibility and government-service logic handled by the backend.

Concretely:

1. Understand the final project requirements and frontend responsibilities.
2. Decide the frontend technology and basic application structure.
3. Plan the browser voice-call interface around LiveKit.
4. Define the major UI elements required for starting, managing and ending a voice session.
5. Keep the frontend structure simple enough to integrate with the backend and voice agent in later weeks.

---

## 2. Day-by-day activity log

### Day 1 — Understanding the frontend requirements

I reviewed the project proposal and discussed with the team how the frontend would fit into the overall Janmitra architecture.

The frontend would not contain the government-scheme eligibility logic or make independent decisions. Its main responsibility would be to provide the browser interface through which the voice agent could be tested.

We identified the main user interaction as a voice call with Janmitra, requiring a clear start/end call action, microphone control and connection feedback.

### Day 2 — Frontend technology planning

We decided to use **Next.js** for the browser application because it provides a suitable React-based structure for building the interface while also allowing server-side functionality required for the LiveKit token route.

LiveKit was selected for handling the real-time voice communication between the browser and the Janmitra agent.

I reviewed how the frontend would communicate with the LiveKit session and how environment variables would be used for the LiveKit configuration.

### Day 3 — Interface structure

I planned the initial interface structure around three main areas:

* A top navigation/header area identifying Janmitra and the voice harness.
* A central call area containing the assistant status, call timer and voice interaction controls.
* Supporting side panels containing session information, connection status and guidance/privacy information.

The goal was to avoid unnecessary UI elements and keep the interface focused on the voice interaction.

### Day 4 — Voice interaction components

I broke the frontend into reusable responsibilities and identified the main `VoiceCall` component as the core of the browser harness.

The component would be responsible for managing the LiveKit session, starting and ending calls, controlling the microphone and displaying the current state of the agent.

I also planned visual states for situations such as Ready, Connecting, Listening, Thinking, Speaking and Connected.

### Day 5 — Frontend integration planning

I discussed with the team how the frontend would integrate with the backend and voice worker.

The frontend would obtain the LiveKit session token through the server-side token route rather than exposing sensitive LiveKit credentials directly in the browser.

This separation keeps the frontend responsible for presentation and session interaction while the backend remains responsible for application logic and secure configuration.

### Day 6 — Initial frontend setup

The initial Next.js frontend structure was organised under `code/frontend`, with separate `app` and `components` directories.

The main page was planned to load the `VoiceCall` component, keeping the page itself lightweight and allowing the voice interface to remain isolated as a reusable component.

---

## 4. Individual work log — Paras (1024170395)

My individual contribution this week focused on the **frontend planning and initial frontend structure**.

### 4.1 Frontend architecture

I worked on defining the browser harness structure using Next.js and React.

The frontend was kept separate from the backend modules so that UI changes would not affect the deterministic government-service logic.

The initial structure consisted of:

* `app/` for Next.js application pages and configuration.
* `components/` for reusable frontend components.
* `VoiceCall.tsx` as the main voice interaction component.
* Environment configuration for LiveKit integration.

### 4.2 VoiceCall component planning

I defined the responsibilities of the main `VoiceCall` component.

It would manage:

* Creating the LiveKit token source.
* Starting a voice session.
* Ending a voice session.
* Enabling and disabling the microphone.
* Tracking the connection state.
* Displaying the agent state.
* Showing the elapsed call time.
* Displaying errors when a call could not be started or the microphone could not be updated.

The component was designed around the actual voice workflow rather than adding unnecessary dashboard functionality.

### 4.3 User interface design

I planned the main visual sections of the voice interface:

* Janmitra branding and environment indicator.
* Current-session information.
* Government scheme guidance heading.
* Voice activity indicator.
* Current agent status.
* Call timer.
* Start/End call button.
* Microphone mute/unmute control.
* Connection status.
* Privacy and guidance information.

This structure was later reflected in the frontend implementation, where the main page renders the `VoiceCall` component and the component provides the complete browser voice-call interface.

### 4.4 LiveKit integration direction

I also worked through how the browser would connect to the LiveKit agent.

The frontend was planned to use the `/api/livekit/token` route to obtain the session token, while keeping the LiveKit API key and secret on the server side.

This was important because sensitive credentials should not be exposed to the browser.

### 4.5 What I did not do

I did not work on the backend data model, eligibility engine or database implementation this week.

Those areas were handled separately by the team, while my focus was the frontend structure and voice interaction design.

---

## 5. Decisions taken this week

| ID   | Decision                                                                | Rationale                                                               | Alternatives rejected                              |
| ---- | ----------------------------------------------------------------------- | ----------------------------------------------------------------------- | -------------------------------------------------- |
| F-01 | Use Next.js for the browser frontend                                    | Provides a suitable React-based structure for the voice harness         | Plain HTML/JS application                          |
| F-02 | Use LiveKit for browser voice communication                             | Provides the real-time communication layer required for the voice agent | Building a custom WebRTC layer                     |
| F-03 | Keep the browser interface as a development/test harness                | The actual citizen channel is planned around telephony/SIP              | Treating the browser as the final citizen channel  |
| F-04 | Keep the main voice interaction inside a reusable `VoiceCall` component | Makes the page simple and keeps voice-session logic isolated            | Putting all logic directly inside `page.tsx`       |
| F-05 | Keep LiveKit credentials server-side                                    | Prevents sensitive API credentials from being exposed to the browser    | Sending credentials directly to the client         |
| F-06 | Keep the interface focused on voice interaction                         | Reduces unnecessary UI complexity and keeps the primary workflow clear  | Building a large dashboard in the initial frontend |

---

## 6. Problems hit and how they were resolved

| Problem                                                                             | Resolution                                                                             |
| ----------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| The frontend could easily become confused with the final citizen-facing application | The browser application was explicitly defined as a voice development/test harness     |
| Voice-session logic could make the main page difficult to maintain                  | The interaction was separated into the `VoiceCall` component                           |
| LiveKit credentials should not be exposed to the client                             | Planned the server-side `/api/livekit/token` route for token generation                |
| The voice assistant has multiple connection states                                  | Planned explicit UI states such as Ready, Connecting, Listening, Thinking and Speaking |

---

## 7. Deliverables produced this week

* Finalised the frontend direction with the team.
* Selected Next.js for the browser interface.
* Planned LiveKit integration for real-time voice communication.
* Defined the structure of the browser voice harness.
* Designed the main `VoiceCall` component responsibilities.
* Planned call, microphone and connection-status controls.
* Established the separation between frontend presentation and backend decision-making.
* Organised the initial `code/frontend` application structure.

---

## 8. Contribution split

| Member                             | Week 2 contribution                                                                                                                                                                                |
| ---------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Dhruv Srivastava (1024170394)      | Joint scope reconciliation and build-order planning. Individually: repository scaffold, configuration layer, structured logging, request-ID propagation and database-layer planning.               |
| Harkamal Singh Lubana (1024170396) | Joint scope reconciliation and build-order planning. Individually: canonical service-record schema, validation rules and persistence model.                                                        |
| Paras (1024170395)                 | Joint scope reconciliation and build-order planning. Individually: frontend architecture planning, Next.js application structure, LiveKit voice-harness design and `VoiceCall` component planning. |

---

## 9. Risks reviewed

| Risk                                                                         | Status this week                                                                       |
| ---------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| Frontend becoming the final citizen channel instead of a development harness | Mitigated by clearly defining the browser application as a test/development interface. |
| Voice-session complexity affecting the UI                                    | Reduced by isolating the interaction inside the `VoiceCall` component.                 |
| Exposure of LiveKit credentials                                              | Mitigated by planning server-side token generation.                                    |
| Frontend/backend integration issues                                          | Remains open and will be addressed during the implementation and integration phases.   |

---

## 10. Carried into Week 3

The frontend work carried into Week 3 includes implementing the planned voice-call interface, connecting the `VoiceCall` component to the LiveKit session, adding call and microphone controls, displaying agent states and integrating the frontend with the backend token route.
