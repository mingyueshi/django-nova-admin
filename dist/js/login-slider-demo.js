// Generated synthetic puzzles. Positions are intentionally public in this local mock.
export const puzzles = [
  {
    'x': 240,
    'y': 42,
    'background': './assets/slider-demo/0-background.png',
    'piece': './assets/slider-demo/0-piece.png',
  },
  {
    'x': 164,
    'y': 44,
    'background': './assets/slider-demo/1-background.png',
    'piece': './assets/slider-demo/1-piece.png',
  },
  {
    'x': 232,
    'y': 57,
    'background': './assets/slider-demo/2-background.png',
    'piece': './assets/slider-demo/2-piece.png',
  },
];

// Reuse the original component's dragging, keyboard, refresh and expiry behavior.
// Only this differently named preview element replaces its HTTP transport.
const BaseSlider = customElements.get('nova-slider');
class DemoSlider extends BaseSlider {
  disconnectedCallback() {
    super.disconnectedCallback();
    this.demoToken = '';
    if (this.field) this.field.value = '';
  }
  async post(action, body) {
    if (action === 'challenge') {
      this.demoIndex = ((this.demoIndex ?? -1) + 1) % puzzles.length;
      this.demoPuzzle = puzzles[this.demoIndex];
      this.demoID = String((this.demoSerial ?? 0) + 1);
      this.demoSerial = Number(this.demoID);
      this.demoExpires = Date.now() + 120000;
      this.demoAttempts = 0;
      this.demoToken = '';
      return {
        challengeId: this.demoID,
        background: this.demoPuzzle.background,
        piece: this.demoPuzzle.piece,
        width: 320,
        height: 160,
        pieceWidth: 44,
        pieceY: this.demoPuzzle.y,
        expiresIn: 120,
        maxAttempts: 5,
      };
    }
    if (action !== 'verify' || body.challengeId !== this.demoID || this.demoAttempts >= 5)
      return { ok: false, code: 'invalid_challenge' };
    if (Date.now() >= this.demoExpires) return { ok: false, code: 'expired' };
    this.demoAttempts++;
    if (Math.abs(body.x - this.demoPuzzle.x) > 4)
      return { ok: false, code: 'incorrect', attemptsRemaining: 5 - this.demoAttempts };
    this.demoToken = 'demo-only-' + this.demoID;
    this.demoProofExpires = Date.now() + 60000;
    return { ok: true, token: this.demoToken, expiresIn: 60 };
  }
  consumeDemoToken() {
    const valid =
      this.getToken() && this.getToken() === this.demoToken && Date.now() < this.demoProofExpires;
    this.demoToken = '';
    if (this.field) this.field.value = '';
    return Boolean(valid);
  }
  connectedCallback() {
    super.connectedCallback();
    this.messages = {
      checking: '正在校验演示拼图…',
      success: '演示验证通过，有效期 {seconds} 秒',
      keyboard: '方向键微调，Enter 校验；也支持鼠标和触屏拖动。',
    };
  }
}
customElements.define('nova-slider-demo', DemoSlider);
