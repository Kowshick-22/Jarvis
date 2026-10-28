import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { JarvisPage } from './JarvisPage';

describe('JARVIS HUD prototype', () => {
  it('renders the command center and clearly labels prototype-only capabilities', () => {
    const html = renderToStaticMarkup(<JarvisPage />);

    expect(html).toContain('J.A.R.V.I.S.');
    expect(html).toContain('Command input');
    expect(html).toContain('Microphone stays off until explicitly activated in the real app.');
    expect(html).toContain('Local model');
    expect(html).toContain('Not connected');
  });

  it('exposes the local memory control as an accessible switch', () => {
    const html = renderToStaticMarkup(<JarvisPage />);

    expect(html).toMatch(/role="switch"[^>]*aria-checked="true"/);
    expect(html).toContain('aria-label="Toggle local memory"');
  });
});
