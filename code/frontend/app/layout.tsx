import type { Metadata } from 'next';
import localFont from 'next/font/local';

import './globals.css';

// Anek Latin by Ek Type: an Indian multi-script superfamily, self-hosted.
const anek = localFont({
  src: './fonts/anek-latin-latin.woff2',
  weight: '100 800',
  variable: '--font-display',
  display: 'swap',
});

// Anek's Devanagari and Gurmukhi cuts, subset to the language names on the page.
const anekDevanagari = localFont({
  src: './fonts/anek-devanagari-hindi.woff2',
  weight: '100 800',
  variable: '--font-deva',
  display: 'swap',
});

const anekGurmukhi = localFont({
  src: './fonts/anek-gurmukhi-punjabi.woff2',
  weight: '100 800',
  variable: '--font-guru',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'Janmitra: government help, in your own words',
  description:
    'Describe your situation by voice, in your own language, and Janmitra explains which government schemes may help and what to do next.',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${anek.variable} ${anekDevanagari.variable} ${anekGurmukhi.variable}`}>
      <body>{children}</body>
    </html>
  );
}
