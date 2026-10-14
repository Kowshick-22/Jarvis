import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  apiFetch: vi.fn(),
  init: vi.fn(),
  capture: vi.fn(),
  identify: vi.fn(),
  register: vi.fn(),
  opt_in_capturing: vi.fn(),
  opt_out_capturing: vi.fn(),
}));
vi.mock('./api', () => ({ apiFetch: mocks.apiFetch }));
vi.mock('posthog-js', () => ({
  default: {
    init: mocks.init,
    capture: mocks.capture,
    identify: mocks.identify,
    register: mocks.register,
    opt_in_capturing: mocks.opt_in_capturing,
    opt_out_capturing: mocks.opt_out_capturing,
  },
}));

const identity = (enabled: boolean) => ({
  enabled, key: enabled ? 'test-key' : '', anon_id: enabled ? 'test-id' : '',
  host: 'https://analytics.example.org', choice_recorded: true,
});
const response = (enabled: boolean) => ({
  ok: true, json: async () => identity(enabled),
});

beforeEach(() => {
  vi.resetModules();
  vi.clearAllMocks();
  mocks.init.mockImplementation((_key, config) => config.loaded(mocks));
});

describe('analytics sharing choice', () => {
  it('does not initialize or send when the backend reports sharing off', async () => {
    mocks.apiFetch.mockResolvedValue(response(false));
    const analytics = await import('./analytics');
    await analytics.initAnalytics();
    analytics.track('app_opened');
    expect(mocks.init).not.toHaveBeenCalled();
    expect(mocks.capture).not.toHaveBeenCalled();
  });

  it('saves only the boolean choice and enables both initialization and capture', async () => {
    mocks.apiFetch.mockResolvedValue(response(true));
    const analytics = await import('./analytics');
    await analytics.saveAnalyticsPreference(true);
    expect(mocks.apiFetch).toHaveBeenCalledWith('/v1/analytics/preference', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: true }),
    });
    expect(mocks.opt_in_capturing).toHaveBeenCalledWith({ captureEventName: false });
    analytics.track('app_opened');
    expect(mocks.capture).toHaveBeenCalledWith('app_opened', {});
  });

  it('can enable after initial startup was disabled, then stop capture immediately', async () => {
    mocks.apiFetch.mockResolvedValue(response(false));
    const analytics = await import('./analytics');
    await analytics.initAnalytics();
    mocks.apiFetch.mockResolvedValue(response(true));
    await analytics.saveAnalyticsPreference(true);
    expect(analytics.isAnalyticsEnabled()).toBe(true);
    mocks.apiFetch.mockResolvedValue(response(false));
    await analytics.saveAnalyticsPreference(false);
    expect(analytics.isAnalyticsEnabled()).toBe(false);
    expect(analytics.getAnonId()).toBe('');
    analytics.track('app_opened');
    expect(mocks.capture).not.toHaveBeenCalled();
    expect(mocks.opt_out_capturing).toHaveBeenCalledOnce();
  });

  it('does not enable capture when saving the choice fails', async () => {
    mocks.apiFetch.mockResolvedValue({ ok: false });
    const analytics = await import('./analytics');
    await expect(analytics.saveAnalyticsPreference(true)).rejects.toThrow('Could not save');
    expect(mocks.init).not.toHaveBeenCalled();
    expect(analytics.isAnalyticsEnabled()).toBe(false);
  });

  it('stops browser capture while a decline is still being saved', async () => {
    mocks.apiFetch.mockResolvedValue(response(true));
    const analytics = await import('./analytics');
    await analytics.initAnalytics();
    let finishSave: (value: ReturnType<typeof response>) => void = () => {};
    mocks.apiFetch.mockImplementationOnce(() => new Promise((resolve) => { finishSave = resolve; }));
    const saving = analytics.saveAnalyticsPreference(false);
    analytics.track('app_opened');
    expect(analytics.isAnalyticsEnabled()).toBe(false);
    expect(mocks.capture).not.toHaveBeenCalled();
    finishSave(response(false));
    await saving;
  });

  it('ignores a stale startup response after an explicit decline', async () => {
    let finishStartup: (value: ReturnType<typeof response>) => void = () => {};
    mocks.apiFetch.mockImplementationOnce(() => new Promise((resolve) => { finishStartup = resolve; }));
    const analytics = await import('./analytics');
    const startup = analytics.initAnalytics();
    mocks.apiFetch.mockResolvedValue(response(false));
    await analytics.saveAnalyticsPreference(false);
    finishStartup(response(true));
    await startup;
    expect(mocks.init).not.toHaveBeenCalled();
    expect(analytics.isAnalyticsEnabled()).toBe(false);
  });
});
