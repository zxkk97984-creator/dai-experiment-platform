<script setup>
import { ref } from 'vue'
import { roles } from '../../views/welcome/welcomeContent.js'

const activeScene = ref(null)
defineEmits(['login'])
</script>

<template>
  <section id="roles" class="roles" aria-label="角色场景">
    <div class="roles-inner">
      <header class="roles-header">
        <p class="roles-eyebrow">角色场景</p>
        <h2 class="roles-title">为每一位参与者设计</h2>
        <p class="roles-sub">学生、教师和管理员，各自拥有专属的工作界面与交互流程。</p>
      </header>

      <div class="roles-grid">
        <div
          v-for="(scene, i) in roles"
          :key="scene.id"
          class="role-card"
          :class="{
            hovered: activeScene === i,
            'role-card--student': scene.id === 'student',
            'role-card--teacher': scene.id === 'teacher',
            'role-card--admin': scene.id === 'admin',
          }"
          @mouseenter="activeScene = i"
          @mouseleave="activeScene = null"
        >
          <div class="role-chrome" aria-hidden="true">
            <span class="role-dot"></span>
            <span class="role-dot"></span>
            <span class="role-dot"></span>
            <span class="role-label">{{ scene.subtitle }}</span>
          </div>
          <div class="role-body">
            <div class="role-sidebar" aria-hidden="true">
              <span v-for="n in 4" :key="n" class="role-sidebar-item" :style="{ '--i': n }"></span>
            </div>
            <div class="role-main">
              <div class="role-header-row">
                <h3 class="role-name">{{ scene.title }}</h3>
              </div>
              <p class="role-desc">{{ scene.desc }}</p>
              <div class="role-features">
                <span v-for="h in scene.highlights" :key="h" class="role-feature">
                  <i class="role-feature-dot"></i>
                  {{ h }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="cta-section">
        <h2 class="cta-title">准备好开始了吗？</h2>
        <p class="cta-desc">免费注册，即刻体验完整的 Python 在线学习与实验平台。</p>
        <button class="cta-btn" @click="$emit('login')">
          立即登录
          <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.roles {
  padding: 80px 56px;
  background: var(--surface-subtle);
}

.roles-inner {
  max-width: 1180px;
  margin: 0 auto;
}

.roles-header {
  margin-bottom: 48px;
}

.roles-eyebrow {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.18em;
  color: var(--info);
  margin: 0 0 12px;
}

.roles-title {
  font-size: 32px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--fg);
  margin: 0 0 12px;
}

.roles-sub {
  font-size: 16px;
  color: var(--muted);
  max-width: 560px;
  line-height: 1.5;
  margin: 0;
}

.roles-grid {
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  gap: 24px;
}

.role-card {
  position: relative;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
  cursor: pointer;
  transition: all 0.35s ease;
}

.role-card--student,
.role-card--teacher,
.role-card--admin { grid-column: span 4; }

.role-card:hover,
.role-card.hovered {
  transform: translateY(-4px);
  box-shadow: 0 16px 48px oklch(0 0 0 / 0.08);
  border-color: var(--border-strong);
}

.role-card--student:hover,
.role-card--student.hovered { border-color: var(--accent); }

.role-card--teacher:hover,
.role-card--teacher.hovered { border-color: var(--info); }

.role-card--admin:hover,
.role-card--admin.hovered { border-color: var(--success); }


.role-chrome {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 12px 16px;
  background: var(--surface-subtle);
  border-bottom: 1px solid var(--surface-subtle);
}

.role-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--border-strong);
}

.role-label {
  margin-left: auto;
  font-size: 11px;
  color: var(--faint);
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.role-body {
  display: flex;
  min-height: 160px;
}

.role-sidebar {
  width: 48px;
  padding: 14px 10px;
  background: var(--surface-subtle);
  border-right: 1px solid var(--surface-subtle);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.role-sidebar-item {
  height: 6px;
  background: var(--border);
  border-radius: var(--radius-sm);
}

.role-sidebar-item:nth-child(1) { width: 85%; }
.role-sidebar-item:nth-child(2) { width: 70%; }
.role-sidebar-item:nth-child(3) { width: 95%; }
.role-sidebar-item:nth-child(4) { width: 60%; }

.role-main {
  flex: 1;
  padding: 20px;
}

.role-header-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.role-name {
  font-size: 17px;
  font-weight: 600;
  color: var(--fg);
  margin: 0;
}

.role-desc {
  font-size: 13px;
  line-height: 1.6;
  color: var(--muted);
  margin: 0 0 14px;
}

.role-features {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.role-feature {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: var(--muted);
}

.role-feature-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--accent);
  flex-shrink: 0;
  transition: transform 0.25s ease;
}

.role-card:hover .role-feature-dot,
.role-card.hovered .role-feature-dot {
  animation: featureDotPulse 0.4s ease forwards;
}
.role-feature:nth-child(1) .role-feature-dot { animation-delay: 0s; }
.role-feature:nth-child(2) .role-feature-dot { animation-delay: 0.06s; }
.role-feature:nth-child(3) .role-feature-dot { animation-delay: 0.12s; }
.role-feature:nth-child(4) .role-feature-dot { animation-delay: 0.18s; }
@keyframes featureDotPulse {
  0% { transform: scale(1); }
  50% { transform: scale(1.8); background: var(--info); }
  100% { transform: scale(1); background: var(--accent); }
}

/* Sidebar items animate on hover */
.role-sidebar-item {
  transition: all 0.3s ease;
}
.role-card:hover .role-sidebar-item,
.role-card.hovered .role-sidebar-item {
  background: var(--border-strong);
  animation: sidebarSlide 0.5s ease forwards;
  animation-delay: calc(var(--i) * 0.08s);
}
@keyframes sidebarSlide {
  0% { transform: translateX(0); }
  50% { transform: translateX(4px); background: var(--accent); }
  100% { transform: translateX(0); background: var(--border-strong); }
}

/* Accent line at bottom */
.role-card::after {
  content: "";
  position: absolute;
  bottom: 0;
  left: 50%;
  width: 0;
  height: 3px;
  border-radius: var(--radius-sm) 3px 0 0;
  transform: translateX(-50%);
  transition: width 0.35s cubic-bezier(0.22, 0.61, 0.36, 1);
}
.role-card--student::after { background: var(--accent); }
.role-card--teacher::after { background: var(--info); }
.role-card--admin::after { background: var(--success); }
.role-card:hover::after,
.role-card.hovered::after {
  width: 50%;
}

/* ====== CTA ====== */
.cta-section {
  margin-top: 72px;
  text-align: center;
  padding: 56px 32px;
  background: linear-gradient(135deg, oklch(0.52 0.095 158 / 0.04), oklch(0.52 0.09 235 / 0.04)), var(--surface);
  border: 1px solid oklch(0.52 0.095 158 / 0.1);
  border-radius: var(--radius-lg);
}

.cta-title {
  font-size: clamp(22px, 2.8vw, 30px);
  font-weight: 700;
  color: var(--fg);
  margin: 0 0 10px;
}

.cta-desc {
  font-size: 15px;
  color: var(--muted);
  margin: 0 0 24px;
}

.cta-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 14px 36px;
  font-size: 15px;
  font-weight: 600;
  font-family: inherit;
  color: var(--surface);
  background: var(--accent);
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 0.2s ease;
}

.cta-btn:hover {
  background: var(--accent-hover);
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}

/* ====== Responsive ====== */
@media (max-width: 1024px) {
  .roles-grid {
    grid-template-columns: repeat(6, 1fr);
  }
  .role-card--student,
  .role-card--teacher,
  .role-card--admin { grid-column: span 3; }
}

@media (max-width: 768px) {
  .roles {
    padding: 48px 24px;
  }
  .roles-grid {
    grid-template-columns: 1fr;
  }
  .role-card--student,
  .role-card--teacher,
  .role-card--admin { grid-column: span 1; }
  .cta-section {
    padding: 40px 24px;
    margin-top: 48px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .role-card:hover,
  .role-card.hovered {
    transform: none;
  }
  .role-card::after { display: none; }
  .role-feature-dot { animation: none !important; }
  .role-sidebar-item { animation: none !important; }
}
</style>
