import Landing from '@/components/Landing';
import VoiceCall from '@/components/VoiceCall';

import './landing.css';

export default function Page() {
  return (
    <main className="landing">
      <Landing />
      <section className="call-section" id="call" aria-labelledby="call-title">
        <h2 id="call-title" className="call-intro">Press call, then tell Janmitra what you need.</h2>
        <VoiceCall />
      </section>
      <footer className="landing-foot">
        <p>
          Janmitra is a UCS503P course project at Thapar Institute of Engineering and Technology.
          Official decisions remain with the responsible government department.
        </p>
      </footer>
    </main>
  );
}
