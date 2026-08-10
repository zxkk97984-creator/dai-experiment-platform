<script setup>
defineProps({
  steps: {
    type: Array,
    required: true,
  },
  isVisible: {
    type: Boolean,
    default: false,
  },
})

</script>

<template>
  <section
    id="learning-loop"
    class="learning-loop"
    :class="{ 'loop--visible': isVisible }"
    aria-labelledby="loop-title"
  >
    <div class="loop-bg" aria-hidden="true">
      <div class="loop-glow loop-glow--left"></div>
      <div class="loop-glow loop-glow--right"></div>
      <div class="loop-grid"></div>
    </div>

    <div class="loop-inner">
      <header class="loop-header">
        <span class="loop-eyebrow">LEARNING CYCLE</span>
        <h2 id="loop-title" class="loop-title">
          学习闭环
          <span class="loop-title-dot" aria-hidden="true"></span>
        </h2>
        <p class="loop-sub">
          从选课到复盘，一次完整的 Python 学习实验旅程。
        </p>
      </header>

      <div class="loop-track" role="list">
        <div class="loop-rail" aria-hidden="true">
          <div class="loop-rail-fill"></div>
        </div>

        <div
          v-for="step in steps"
          :key="step.n"
          class="loop-node"
          role="listitem"
        >
          <div class="node-circle">
            <span class="node-num" aria-hidden="true">{{ step.n }}</span>
            <svg
              class="node-check"
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              aria-hidden="true"
            >
              <path
                d="M5 13l4 4L19 7"
                stroke="currentColor"
                stroke-width="2.5"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </svg>
          </div>
          <div class="node-body">
            <strong class="node-title">{{ step.title }}</strong>
            <p class="node-desc">{{ step.desc }}</p>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.learning-loop {
  position: relative;
  overflow: hidden;
  background: #14213b;
  padding: 80px 0 72px;
  isolation: isolate;
}

.loop-bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 0;
}

.loop-glow {
  position: absolute;
  width: 500px;
  height: 500px;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.18;
  animation: loopGlowDrift 16s ease-in-out infinite alternate;
}
.loop-glow--left {
  top: -40%;
  left: -10%;
  background: radial-gradient(circle, rgba(36, 103, 237, 0.5), transparent 70%);
}
.loop-glow--right {
  bottom: -30%;
  right: -8%;
  background: radial-gradient(circle, rgba(115, 89, 237, 0.4), transparent 70%);
  animation-delay: -8s;
}

@keyframes loopGlowDrift {
  0% { transform: translate(0, 0); }
  100% { transform: translate(24px, -18px); }
}

.loop-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: radial-gradient(ellipse 60% 60% at 50% 50%, black 30%, transparent 70%);
}

.loop-inner {
  position: relative;
  z-index: 1;
  max-width: 1120px;
  margin: 0 auto;
  padding: 0 40px;
}

.loop-header {
  text-align: center;
  margin-bottom: 52px;
}

.loop-eyebrow {
  display: inline-block;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.16em;
  color: rgba(255, 255, 255, 0.45);
  margin-bottom: 12px;
}

.loop-title {
  margin: 0;
  font-family: "Segoe UI Variable Display", "PingFang SC", "Microsoft YaHei", sans-serif;
  font-size: clamp(24px, 3.2vw, 34px);
  font-weight: 750;
  letter-spacing: -0.025em;
  color: #fff;
}

.loop-title-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #58dda7;
  margin-left: 6px;
  vertical-align: middle;
  animation: dotPulse 2s ease-in-out infinite;
}

@keyframes dotPulse {
  0%, 100% { opacity: 0.5; transform: scale(0.8); }
  50% { opacity: 1; transform: scale(1); }
}

.loop-sub {
  margin: 10px 0 0;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.5);
  line-height: 1.6;
}

.loop-track {
  position: relative;
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 32px 0;
}

.loop-rail {
  position: absolute;
  top: 80px;
  left: 44px;
  right: 44px;
  height: 2px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 2px;
}

.loop-rail-fill {
  width: 0;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(
    90deg,
    #2467ed,
    #7359ed 50%,
    #58dda7
  );
  transition: width 1.2s cubic-bezier(0.22, 0.61, 0.36, 1);
}

.loop--visible .loop-rail-fill {
  width: 100%;
}

.loop-node {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  flex: 1;
  min-width: 0;
  padding-top: 34px;
  opacity: 0;
  transform: translateY(18px);
  transition: opacity 0.52s cubic-bezier(0.22, 0.61, 0.36, 1),
              transform 0.52s cubic-bezier(0.22, 0.61, 0.36, 1);
}

.loop-node:nth-child(2) { transition-delay: 120ms; }
.loop-node:nth-child(3) { transition-delay: 240ms; }
.loop-node:nth-child(4) { transition-delay: 360ms; }
.loop-node:nth-child(5) { transition-delay: 480ms; }
.loop-node:nth-child(6) { transition-delay: 600ms; }

.loop--visible .loop-node {
  opacity: 1;
  transform: translateY(0);
}

.node-circle {
  position: relative;
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.06);
  border: 2px solid rgba(255, 255, 255, 0.12);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 18px;
  transition: background 0.5s ease,
              border-color 0.5s ease,
              box-shadow 0.5s ease;
}

.loop--visible .node-circle {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(36, 103, 237, 0.55);
  box-shadow: 0 0 24px rgba(36, 103, 237, 0.15);
}

.node-num,
.node-check {
  position: absolute;
  transition: opacity 0.3s ease, transform 0.35s ease;
}

.node-num {
  font-family: "Cascadia Code", "Fira Code", "JetBrains Mono", monospace;
  font-size: 14px;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.5);
}

.loop--visible .node-num {
  opacity: 0;
  transform: scale(0.6);
}

.node-check {
  opacity: 0;
  transform: scale(0.6);
  color: #58dda7;
  transition-delay: 0.5s;
}

.loop--visible .node-check {
  opacity: 1;
  transform: scale(1);
}

.node-body {
  padding: 0 4px;
}

.node-title {
  display: block;
  font-size: 15px;
  font-weight: 650;
  color: #fff;
  letter-spacing: -0.005em;
  margin-bottom: 6px;
}

.node-desc {
  margin: 0;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
  line-height: 1.55;
  max-width: 180px;
  margin-left: auto;
  margin-right: auto;
}

@media (max-width: 860px) {
  .learning-loop {
    padding: 56px 0 48px;
  }

  .loop-inner {
    padding: 0 24px;
  }

  .loop-track {
    flex-direction: column;
    align-items: stretch;
    gap: 0;
    padding: 12px 0;
  }

  .loop-node {
    flex-direction: row;
    text-align: left;
    padding: 20px 0 20px 52px;
    align-items: center;
    transition-delay: 0ms;
  }

  .node-circle {
    position: absolute;
    left: 0;
    top: 50%;
    width: 40px;
    height: 40px;
    margin-bottom: 0;
  }

  .node-body {
    margin-left: 0;
  }

  .node-desc {
    max-width: none;
    margin-left: 0;
    margin-right: 0;
  }

  .loop-rail {
    top: 0;
    bottom: 0;
    left: 19px;
    right: auto;
    width: 2px;
    height: auto;
  }

  .loop-rail-fill {
    width: 100%;
    height: 0;
    transition: height 1.2s cubic-bezier(0.22, 0.61, 0.36, 1);
  }

  .loop--visible .loop-rail-fill {
    width: 100%;
    height: 100%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .loop-node {
    opacity: 1;
    transform: none;
    transition: none;
  }

  .node-circle {
    transition: none;
  }

  .loop--visible .node-num {
    opacity: 1;
    transform: none;
  }

  .node-check {
    display: none;
  }

  .loop-glow {
    animation: none;
    opacity: 0.06;
  }

  .loop-rail-fill {
    transition: none;
  }

  .loop--visible .loop-rail-fill {
    width: 100%;
  }
}
</style>