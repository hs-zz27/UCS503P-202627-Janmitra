# Janmitra — Weekly Engineering Journal

## Week 3 — Frontend Implementation: VoiceCall Interface, LiveKit Integration and Responsive UI

| Field                 | Value                                                                                                                                                                                                                                                                                                                                                   |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Course                | UCS503 / UCS503P — Software Engineering                                                                                                                                                                                                                                                                                                                 |
| Institute             | Thapar Institute of Engineering and Technology, Patiala                                                                                                                                                                                                                                                                                                 |
| Project               | Janmitra — a voice-first civic scheme guidance platform                                                                                                                                                                                                                                                                                                 |
| Week                  | 18 – 24 August 2026                                                                                                                                                                                                                                                                                                                                     |
| Member                | Paras (1024170395)                                                                                                                                                                                                                                                                                                                                      |
| Status at end of week | The browser frontend was implemented as a functional Next.js voice-call harness. The `VoiceCall` component was connected to the LiveKit session, call and microphone controls were implemented, connection and agent states were displayed, call timing and error handling were added, and the interface was styled as a responsive three-panel layout. |

> On individual logs. Sections 1, 2, 5, 6, 7, 8 and 9 are common to the team. Section 4 is this member's individual work log.

---

## 1. Objective for the week

The main objective this week was to move the frontend from the planning stage into an actual working browser interface.

The browser application is intended as the development harness for interacting with the Janmitra LiveKit voice agent. Therefore, the frontend needed to provide a reliable interface for starting and ending a call, controlling the microphone, showing connection status and giving the user feedback about the current state of the voice agent.

The implementation was organised around the existing Next.js application structure, with the main page rendering the reusable `VoiceCall` component. The frontend also needed to communicate with the server-side LiveKit token route without exposing the LiveKit API credentials to the browser.

Concretely:

1. Implement the planned `VoiceCall` React component.
2. Connect the frontend to the LiveKit session.
3. Implement Start Call and End Call functionality.
4. Implement microphone mute/unmute controls.
5. Display connection and agent states.
6. Add a call timer and error handling.
7. Build the main Janmitra interface and responsive styling.
8. Keep the frontend separated from the backend decision-making logic.

---

## 2. Day-by-day activity log

### Day 1 — Frontend implementation structure

I moved from the Week 2 frontend plan to implementation.

The existing `code/frontend` structure was used with the Next.js `app` directory and a separate `components` directory. The main `page.tsx` was kept intentionally small and renders the `VoiceCall` component, allowing the voice interaction logic to remain isolated from the page itself.

### Day 2 — LiveKit session integration

I implemented the LiveKit session inside `VoiceCall.tsx`.

The component uses LiveKit React components and creates a token source through the `/api/livekit/token` endpoint. The session is configured with the Janmitra agent name, a generated participant identity and the browser harness channel metadata.

This allowed the frontend to act as a browser participant in the Janmitra voice session without putting the core voice-agent logic inside the frontend.

### Day 3 — Start and End Call functionality

The call controls were implemented.

The Start Call action clears previous errors, resets the timer and microphone state, and starts the LiveKit session with microphone access enabled.

The End Call action terminates the session and resets the timer and microphone state.

The Start Call button is also disabled while the session is connecting so that repeated clicks cannot initiate multiple connection attempts.

### Day 4 — Microphone control and session states

I implemented microphone mute/unmute functionality using the LiveKit local participant microphone control.

The frontend tracks the microphone state and changes the icon and accessible label between microphone and microphone-off states.

I also implemented the session status logic so that the interface can display:

* Ready
* Connecting
* Connected
* Listening
* Thinking
* Speaking

This gives the user immediate feedback about what the voice assistant is currently doing.

### Day 5 — Call timer and error handling

A call timer was added to the interface.

The timer starts when the LiveKit session becomes active and stops when the session is no longer connected. The displayed value is formatted as minutes and seconds.

Error handling was also added around call start, call termination and microphone changes. Errors are stored in component state and displayed to the user through an alert-style message instead of silently failing.

### Day 6 — UI implementation and responsive styling

I implemented the main Janmitra interface using the planned three-section layout.

The interface contains:

* Janmitra branding and Voice Harness indicator.
* Current session information.
* Government scheme guidance context.
* Voice activity animation.
* Current assistant status.
* Call timer.
* Start/End Call button.
* Microphone mute/unmute button.
* Connection status.
* Privacy and guidance information.

The styling was implemented in `globals.css`, including the three-column desktop layout, voice animation, button states, connection indicator and responsive breakpoints for smaller screens.

---

## 4. Individual work log — Paras (1024170395)

My individual contribution this week focused on implementing the **frontend voice-call harness and user interface**.

### 4.1 `VoiceCall.tsx` implementation

The main frontend work was implemented in `components/VoiceCall.tsx`.

The component uses:

* `SessionProvider`
* `RoomAudioRenderer`
* `useSession`
* `useAgent`
* LiveKit `TokenSource`
* React state and effects
* Lucide icons for interface controls

The component acts as the main bridge between the browser UI and the LiveKit voice session.

### 4.2 LiveKit session setup

I implemented the LiveKit token source using:

`/api/livekit/token`

The session is configured with:

* The Janmitra agent name.
* A generated browser participant identity.
* `Janmitra citizen` as the participant name.
* `channel: harness` as the agent metadata.

This keeps the browser interaction connected to the correct voice agent while using the server-side token endpoint for authentication.

### 4.3 Start and End Call controls

The Start Call functionality was implemented to:

* Clear existing errors.
* Reset the timer.
* Reset microphone state.
* Start the LiveKit session.
* Enable the browser microphone.

The End Call functionality:

* Ends the LiveKit session.
* Resets the timer.
* Restores the microphone state.
* Clears the active session state.

The same button changes between `Start call` and `End call` depending on the connection state.

### 4.4 Microphone mute/unmute

A dedicated microphone button was implemented for active calls.

The button uses LiveKit's local participant API to enable or disable the microphone. Its icon, label and visual state change according to whether the microphone is muted.

This makes microphone control available without interrupting the ongoing voice session.

### 4.5 Agent and connection status

The frontend was implemented to determine the current status from the LiveKit connection and agent state.

The displayed status changes between:

`Ready → Connecting → Connected → Listening / Thinking / Speaking`

This status is displayed both in the central call area and in the connection panel.

### 4.6 Voice activity indicator

A visual voice signal was implemented using five animated bars.

When a call is active, the bars animate with different delays to give visual feedback that the voice interface is active. When no call is active, the animation is disabled.

A reduced-motion media query was also included so that the animation is disabled for users who prefer reduced motion.

### 4.7 Call timer

The frontend tracks elapsed call time using React state and an interval that runs only while the LiveKit session is connected.

The timer is displayed in `MM:SS` format and resets when the call ends.

### 4.8 Error handling

Error handling was implemented for the main interactive operations.

If starting the call fails, the frontend displays the returned error message. Similar handling was added for microphone updates.

The error is rendered with an alert role so that the failure is visible to the user rather than being hidden in the console.

### 4.9 Interface and responsive design

The frontend was styled as a clean three-section interface:

* Left panel — current session and guidance information.
* Centre panel — main Janmitra voice interaction.
* Right panel — connection information.

The CSS also contains responsive breakpoints. Below 900px, the side panels are hidden and the central call stage occupies the available width. A second breakpoint adjusts the mobile spacing and heading size.

### 4.10 Main page integration

The Next.js `page.tsx` was kept minimal and imports the `VoiceCall` component directly.

This makes `VoiceCall` the primary frontend interface while keeping the page-level implementation simple.

### 4.11 What I did not do

I did not implement the deterministic eligibility evaluator, catalogue logic, database models or backend service modules.

Those parts were handled by the other team members. My work during this week was concentrated on the browser frontend, LiveKit session interaction and UI implementation.

---

## 5. Decisions taken this week

| ID   | Decision                                                                  | Rationale                                                         | Alternatives rejected                             |
| ---- | ------------------------------------------------------------------------- | ----------------------------------------------------------------- | ------------------------------------------------- |
| F-07 | Keep `VoiceCall` as the main frontend interaction component               | Keeps LiveKit and call-state logic isolated                       | Putting the logic directly in `page.tsx`          |
| F-08 | Use the server-side token endpoint for LiveKit sessions                   | Prevents API credentials from being exposed to the browser        | Generating tokens directly in client-side code    |
| F-09 | Disable Start Call while connecting                                       | Prevents repeated connection attempts                             | Allowing repeated button presses                  |
| F-10 | Derive displayed status from LiveKit connection and agent state           | Keeps the UI synchronized with the actual session                 | Maintaining a separate manually controlled status |
| F-11 | Reset timer and microphone state after ending a call                      | Ensures a new call starts from a clean state                      | Preserving the previous session state             |
| F-12 | Use a responsive three-panel desktop layout with a simplified mobile view | Keeps the interface usable across screen sizes                    | Fixed desktop-only layout                         |
| F-13 | Include reduced-motion support for voice animation                        | Avoids unnecessary animation for users who request reduced motion | Always running the animation                      |

---

## 6. Problems hit and how they were resolved

### 6.1 Multiple frontend states

The voice session has more states than simply connected/disconnected.

The interface therefore derives its status from both the LiveKit connection state and the agent state. This allows the user to distinguish between connecting, listening, thinking and speaking.

### 6.2 Protecting LiveKit credentials

The browser should not receive the LiveKit API key and secret.

The frontend therefore uses the `/api/livekit/token` endpoint as its token source, while the sensitive values remain on the server side.

### 6.3 Preventing stale call state

Starting and ending calls could leave stale timer or microphone state behind.

The `start()` and `stop()` functions explicitly reset the timer, microphone state and error state so every call begins cleanly.

### 6.4 Voice feedback without unnecessary complexity

Because the application is voice-first, a traditional chat-style interface was unnecessary for the current harness.

A visual voice-signal animation and clear status text were used instead to communicate that the assistant is active and whether it is listening, thinking or speaking.

---

## 7. Deliverables produced this week

* Functional `VoiceCall.tsx` component.
* LiveKit session integration.
* Server-side LiveKit token endpoint integration.
* Start Call functionality.
* End Call functionality.
* Microphone mute/unmute control.
* LiveKit connection-state display.
* Agent-state display for Listening, Thinking and Speaking.
* Call timer.
* Error handling for call and microphone operations.
* Voice activity animation.
* Janmitra branding and session-information panels.
* Responsive frontend styling.
* Minimal Next.js page integration.

The repository currently contains the browser harness under `code/frontend`, with `app/page.tsx`, `app/globals.css`, `components/VoiceCall.tsx` and the LiveKit token route forming the core frontend implementation.

---

## 8. Contribution split

| Member                             | Week 3 contribution                                                                                                                                                                                                                                            |
| ---------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Dhruv Srivastava (1024170394)      | Joint boundary-case derivation and the `applies_when` design review. Individually: catalogue service, conversation service and TTG clock, handoff trigger rules and state machine, audit writer.                                                               |
| Harkamal Singh Lubana (1024170396) | Joint boundary-case derivation and the `applies_when` design review. Individually: eligibility evaluator, answer validation and coercion, next-question selection and document-checklist builder.                                                              |
| Paras (1024170395)                 | Joint boundary-case derivation and the `applies_when` design review. Individually: browser frontend implementation, `VoiceCall` LiveKit integration, call controls, microphone control, connection/agent status, call timer, error handling and responsive UI. |

---

## 9. Risks reviewed

| Risk                                                  | Status this week                                                                                                                            |
| ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| LiveKit session or browser microphone failure         | Error handling was added to the frontend; actual environment configuration remains an integration dependency.                               |
| Frontend becoming coupled to backend decision logic   | Avoided. The frontend remains responsible for the voice-session interface while eligibility and catalogue logic remain in backend services. |
| Sensitive LiveKit credentials reaching the browser    | Mitigated through the server-side token route.                                                                                              |
| Responsive behaviour on smaller screens               | Addressed through CSS breakpoints and simplified mobile layout.                                                                             |
| Voice-session state becoming inconsistent with the UI | Reduced by deriving displayed status from the LiveKit session and agent state.                                                              |
| Telephony / SIP provisioning delay                    | Unchanged; the browser harness remains available independently of the future telephone channel.                                             |

---

## 10. Carried into Week 4

The frontend work carried into Week 4 includes testing the browser voice harness against the running backend and LiveKit worker, validating microphone and audio behaviour, handling integration failures, and refining the interface based on actual voice-session behaviour.
