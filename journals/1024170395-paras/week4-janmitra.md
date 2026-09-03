# Janmitra — Weekly Engineering Journal

## Week 4 — Frontend Integration, Testing and UI Refinement

| Field                 | Value                                                                                                                                                                                                                                                                                                                                                                                         |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Course                | UCS503 / UCS503P — Software Engineering                                                                                                                                                                                                                                                                                                                                                       |
| Institute             | Thapar Institute of Engineering and Technology, Patiala                                                                                                                                                                                                                                                                                                                                       |
| Project               | Janmitra — a voice-first civic scheme guidance platform                                                                                                                                                                                                                                                                                                                                       |
| Week                  | 25 – 31 August 2026                                                                                                                                                                                                                                                                                                                                                                           |
| Member                | Paras (1024170395)                                                                                                                                                                                                                                                                                                                                                                            |
| Status at end of week | The frontend voice harness was integrated and refined around the implemented LiveKit voice workflow. The browser interface was tested for call lifecycle, microphone control, agent-state feedback, timer behaviour, error handling and responsive layout. Frontend issues were identified and resolved while keeping the browser harness separated from the backend decision-making modules. |

---

## 1. Objective for the week

The main objective this week was to move the frontend from basic implementation towards a more stable and testable voice interaction interface.

After implementing the main `VoiceCall` component in Week 3, the focus was on checking the complete user interaction flow and improving the interface wherever required.

The frontend needed to reliably handle:

1. Starting a voice session.
2. Connecting the browser to the LiveKit room.
3. Displaying the current connection state.
4. Showing the voice agent's current activity.
5. Muting and unmuting the microphone.
6. Ending a voice session cleanly.
7. Resetting the call timer and UI state.
8. Displaying errors instead of silently failing.
9. Maintaining a usable layout on smaller screens.

The frontend continued to act as a browser-based voice harness rather than implementing the backend eligibility or scheme-selection logic.

---

## 2. Day-by-day activity log

### Day 1 — Frontend integration review

I reviewed the implemented frontend against the complete Janmitra workflow.

The main focus was checking whether the browser interface correctly represented the different states of the LiveKit voice session.

I verified the responsibilities of `page.tsx`, `VoiceCall.tsx`, the LiveKit token route and the global stylesheet to make sure that the frontend components remained properly separated.

### Day 2 — Voice-call lifecycle testing

I tested the complete call lifecycle:

**Ready → Connecting → Connected → Active voice interaction → End Call → Ready**

The Start Call and End Call controls were checked for correct state transitions.

I also verified that the Start Call action does not remain available for repeated connection attempts while a session is already being established.

### Day 3 — Microphone and audio behaviour

I tested the microphone control during an active session.

The mute/unmute button was checked to ensure that the local participant's microphone state changes correctly and that the interface reflects the current state.

The frontend was also checked for correct handling when microphone-related operations fail.

### Day 4 — Agent status and voice feedback

I worked on validating the visual feedback shown while the agent is operating.

The frontend displays different states depending on the LiveKit connection and agent state, including:

* Ready
* Connecting
* Connected
* Listening
* Thinking
* Speaking

The voice activity animation was checked against the active call state so that it does not appear as if the assistant is active when there is no call.

### Day 5 — Timer and error-state testing

The call timer behaviour was tested across the call lifecycle.

The timer starts with the active session and stops when the session ends. It is reset when a new call is started.

Error handling was also checked for call-start and microphone operations. The interface displays an error message when an operation fails instead of leaving the user without feedback.

### Day 6 — Responsive UI refinement

I reviewed the three-panel interface at different screen sizes.

The responsive CSS was refined around the existing breakpoints so that the central voice interface remains usable when the side panels are hidden on smaller screens.

Spacing, heading sizes, call controls and the voice activity section were checked to prevent the interface from becoming crowded on smaller displays.

---

## 4. Individual work log — Paras (1024170395)

My individual contribution this week focused on **frontend integration, testing, debugging and UI refinement**.

### 4.1 Complete voice-call workflow

I tested the browser voice harness as a complete user workflow instead of testing individual buttons independently.

The expected flow was:

**Start Call → Connect → Voice Interaction → Microphone Control → End Call**

The frontend state was checked at each stage to ensure that the UI represented the actual LiveKit session state.

### 4.2 LiveKit connection-state handling

The frontend was checked for correct handling of the LiveKit connection lifecycle.

The UI uses the session connection state to determine whether the application is:

* Ready
* Connecting
* Connected

This prevents the interface from displaying an active call before the LiveKit session is actually established.

### 4.3 Agent-state handling

The agent state was integrated into the displayed frontend status.

The interface can distinguish between the assistant listening, thinking and speaking.

This was important because a voice-first application needs to communicate what the assistant is doing without relying on a conventional chat interface.

### 4.4 Microphone state validation

The microphone control was tested during active sessions.

The frontend updates the local participant's microphone state and changes the button icon and accessible label accordingly.

The control is only presented as an active interaction when a call is running.

### 4.5 Call timer validation

The timer was checked for correct behaviour when:

* A call starts.
* The session becomes connected.
* The call remains active.
* The call ends.
* A new call starts.

The timer resets between sessions so that information from the previous call is not carried into a new call.

### 4.6 Error handling validation

I checked the error states associated with the main frontend operations.

The interface displays errors using a dedicated alert message when call or microphone operations fail.

This provides visible feedback to the user and avoids leaving the interface in an apparently frozen state.

### 4.7 Voice activity animation

The voice activity indicator was reviewed as part of the overall interaction feedback.

The five-bar animation provides a visual indication that the voice interface is active.

The CSS also contains reduced-motion handling so that the animation can be disabled when the user prefers reduced motion.

### 4.8 Responsive frontend

The responsive behaviour of the interface was reviewed.

The desktop version uses the three-section structure:

* Current session / guidance.
* Main Janmitra voice interaction.
* Connection information.

At smaller widths, the side panels are hidden and the central interaction area is prioritised.

This keeps the most important functionality—the voice call—available on smaller screens.

### 4.9 Frontend/backend separation

During integration testing, I maintained the separation between the frontend and backend responsibilities.

The frontend handles:

* User controls.
* LiveKit connection.
* Microphone interaction.
* Session state.
* Agent-state display.
* Timer.
* Error feedback.

The backend continues to handle application logic and secure LiveKit token generation.

This prevents frontend UI logic from becoming coupled with the deterministic eligibility and scheme-processing modules.

### 4.10 Frontend code organisation

The final frontend structure keeps the main page lightweight:

`app/page.tsx`

renders:

`components/VoiceCall.tsx`

while the overall appearance and responsive behaviour are handled through:

`app/globals.css`

The LiveKit token functionality remains under the API route rather than being implemented directly in the client component.

---

## 5. Decisions taken this week

| ID   | Decision                                                              | Rationale                                                           | Alternatives rejected                                   |
| ---- | --------------------------------------------------------------------- | ------------------------------------------------------------------- | ------------------------------------------------------- |
| F-14 | Test the complete call lifecycle rather than individual controls only | Finds state-transition issues between components                    | Testing buttons independently                           |
| F-15 | Derive displayed connection status from the actual LiveKit state      | Keeps UI feedback consistent with the real session                  | Maintaining manually controlled connection status       |
| F-16 | Keep microphone control inside the active-call state                  | Prevents invalid microphone operations before connection            | Showing active microphone controls before a call        |
| F-17 | Reset timer and microphone state between calls                        | Prevents stale information from previous sessions                   | Reusing previous session state                          |
| F-18 | Keep voice activity animation tied to active voice interaction        | Provides useful visual feedback without constantly animating        | Always displaying animation                             |
| F-19 | Prioritise the central voice interface on small screens               | Preserves the primary application function on mobile-sized displays | Keeping the complete three-column layout on all screens |
| F-20 | Keep frontend independent from eligibility logic                      | Maintains clean frontend/backend boundaries                         | Implementing decision logic in React                    |

---

## 6. Problems hit and how they were resolved

### 6.1 UI state and actual connection state

A voice application can easily display an incorrect state if the UI uses manually maintained flags.

The frontend therefore uses the actual LiveKit session state and agent state when determining what status should be displayed.

### 6.2 State reset after ending a call

Ending a session needs to clean up more than the connection itself.

The timer, microphone state and active-session state are reset so that the next call starts from a predictable state.

### 6.3 Microphone operation failures

Microphone operations can fail because of browser permissions or unavailable devices.

The frontend catches these errors and exposes them through the interface rather than silently ignoring them.

### 6.4 Maintaining usability on smaller screens

The three-panel desktop layout does not provide enough space on smaller screens.

Responsive CSS was therefore used to prioritise the main voice interaction and hide secondary panels when the viewport becomes narrow.

### 6.5 Providing useful feedback in a voice-first interface

Since the application does not depend on a traditional chat window, the user needs another way to understand what the assistant is doing.

Connection status, agent-state labels, call timing and the voice activity animation provide this feedback.

---

## 7. Deliverables produced this week

* Tested the complete browser voice-call lifecycle.
* Validated LiveKit connection-state handling.
* Validated agent-state feedback.
* Tested microphone mute/unmute behaviour.
* Validated call timer behaviour.
* Tested frontend error handling.
* Reviewed and refined the voice activity indicator.
* Tested responsive behaviour of the three-panel interface.
* Maintained frontend/backend separation.
* Refined the browser voice harness for integration with the rest of Janmitra.

---

## 8. Contribution split

| Member                             | Week 4 contribution                                                                                                                                                                       |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Dhruv Srivastava (1024170394)      | Backend integration, logging/audit verification, service-level testing and system-level debugging.                                                                                        |
| Harkamal Singh Lubana (1024170396) | Eligibility/evaluator integration, validation testing, scheme-rule verification and backend functional testing.                                                                           |
| Paras (1024170395)                 | Frontend integration and testing, LiveKit voice-session lifecycle validation, microphone and call controls, agent-state feedback, timer/error-state testing and responsive UI refinement. |

---

## 9. Risks reviewed

| Risk                                                       | Status this week                                                                              |
| ---------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| Browser microphone permissions affecting voice interaction | Error handling added; environment permissions remain a runtime dependency.                    |
| Incorrect UI state during LiveKit connection               | Reduced by deriving displayed state from the actual session and agent state.                  |
| Stale state between consecutive calls                      | Addressed through explicit reset behaviour.                                                   |
| Poor usability on smaller screens                          | Addressed through responsive layout rules.                                                    |
| Frontend becoming dependent on backend business logic      | Avoided by maintaining the frontend/backend separation.                                       |
| LiveKit configuration issues                               | Remains an environment/integration dependency and requires correct server-side configuration. |

---

## 10. Carried into Week 5

The frontend work carried forward includes further end-to-end testing with the complete Janmitra stack, testing the voice workflow with realistic scheme-related conversations, addressing integration issues discovered during team testing, and making final UI improvements based on observed user interaction.
