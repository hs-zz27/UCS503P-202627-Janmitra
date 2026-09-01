import type { Metadata } from 'next';

import './globals.css';

export const metadata: Metadata = {
  title: 'Janmitra Voice Harness',
  description: 'Development voice channel for Janmitra',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
