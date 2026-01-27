import { useState, useEffect } from 'react'
import { api } from '../src/utils/api'

interface SplashScreenProps {
  onComplete: () => void
}

export default function SplashScreen({ onComplete }: SplashScreenProps) {
  const [stage, setStage] = useState<'black' | 'hi' | 'greeting' | 'welcome' | 'white' | 'complete'>('black')
  const [showHi, setShowHi] = useState(false)
  const [showGreeting, setShowGreeting] = useState(false)
  const [showWelcome, setShowWelcome] = useState(false)

  useEffect(() => {
    const sequence = async () => {
      // 1. 屏幕先是黑的 (500ms)
      await new Promise(resolve => setTimeout(resolve, 500))

      // 2. 浮出文字"嗨" - 淡入
      setStage('hi')
      // 延迟一点再显示，确保DOM已更新
      await new Promise(resolve => setTimeout(resolve, 50))
      setShowHi(true)
      // 等待淡入动画完成 + 显示时间
      await new Promise(resolve => setTimeout(resolve, 1200 + 1500))

      // 3. "嗨"消失 - 淡出
      setShowHi(false)
      // 等待淡出动画完成
      await new Promise(resolve => setTimeout(resolve, 1200 + 300))

      // 4. 浮出文字"别来无恙" - 淡入
      setStage('greeting')
      setShowGreeting(false) // 先重置
      await new Promise(resolve => setTimeout(resolve, 50))
      setShowGreeting(true)
      // 等待淡入动画完成 + 显示时间
      await new Promise(resolve => setTimeout(resolve, 1200 + 2000))

      // 5. "别来无恙"消失 - 淡出
      setShowGreeting(false)
      // 等待淡出动画完成
      await new Promise(resolve => setTimeout(resolve, 1200 + 300))

      // 6. 浮出文字"欢迎使用RuaBot框架" - 淡入
      setStage('welcome')
      setShowWelcome(false) // 先重置
      await new Promise(resolve => setTimeout(resolve, 50))
      setShowWelcome(true)
      // 等待淡入动画完成 + 显示时间
      await new Promise(resolve => setTimeout(resolve, 1200 + 2000))

      // 7. "欢迎使用RuaBot框架"消失 - 淡出
      setShowWelcome(false)
      // 等待淡出动画完成
      await new Promise(resolve => setTimeout(resolve, 1200 + 300))

      // 8. 屏幕渐变白
      setStage('white')
      await new Promise(resolve => setTimeout(resolve, 800))

      // 7. 完成，显示主界面
      setStage('complete')
      
      // 标记已显示过开屏动画（在动画完成后立即标记）
      try {
        const result = await api.markSplashScreenShown()
        console.log('Splash screen marked as shown:', result)
      } catch (error) {
        console.error('Failed to mark splash screen as shown:', error)
      }
      
      onComplete()
    }

    sequence()
  }, [onComplete])

  const getBackgroundColor = () => {
    switch (stage) {
      case 'black':
        return 'bg-black'
      case 'hi':
      case 'greeting':
      case 'welcome':
        return 'bg-black'
      case 'white':
        return 'bg-white'
      case 'complete':
        return 'bg-white'
      default:
        return 'bg-black'
    }
  }

  return (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center transition-colors ${getBackgroundColor()}`}
      style={{ transitionDuration: '800ms' }}
    >
      {/* "嗨"文字 - 始终在DOM中，通过opacity和transform控制显示 */}
      <div
        className="absolute flex flex-col items-center justify-center"
        style={{
          opacity: stage === 'hi' && showHi ? 1 : 0,
          transform: stage === 'hi' && showHi ? 'scale(1) translateY(0)' : 'scale(0.95) translateY(-20px)',
          transition: 'opacity 1.2s ease-in-out, transform 1.2s ease-in-out',
          pointerEvents: stage === 'hi' && showHi ? 'auto' : 'none',
          willChange: 'opacity, transform',
        }}
      >
        <div
          className="text-white font-bold"
          style={{
            fontSize: '8rem',
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", sans-serif',
          }}
        >
          嗨
        </div>
        <div
          className="text-white text-3xl mt-6 font-medium"
          style={{
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", sans-serif',
          }}
        >
          Hi
        </div>
      </div>

      {/* "别来无恙"文字 - 始终在DOM中，通过opacity和transform控制显示 */}
      <div
        className="absolute flex flex-col items-center justify-center"
        style={{
          opacity: stage === 'greeting' && showGreeting ? 1 : 0,
          transform: stage === 'greeting' && showGreeting ? 'scale(1) translateY(0)' : 'scale(0.95) translateY(-20px)',
          transition: 'opacity 1.2s ease-in-out, transform 1.2s ease-in-out',
          pointerEvents: stage === 'greeting' && showGreeting ? 'auto' : 'none',
          willChange: 'opacity, transform',
        }}
      >
        <div
          className="text-white font-bold"
          style={{
            fontSize: '6rem',
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", sans-serif',
          }}
        >
          别来无恙
        </div>
        <div
          className="text-white text-3xl mt-6 font-medium"
          style={{
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", sans-serif',
          }}
        >
          Long time no see
        </div>
      </div>

      {/* "欢迎使用RuaBot框架"文字 - 始终在DOM中，通过opacity和transform控制显示 */}
      <div
        className="absolute flex flex-col items-center justify-center"
        style={{
          opacity: stage === 'welcome' && showWelcome ? 1 : 0,
          transform: stage === 'welcome' && showWelcome ? 'scale(1) translateY(0)' : 'scale(0.95) translateY(-20px)',
          transition: 'opacity 1.2s ease-in-out, transform 1.2s ease-in-out',
          pointerEvents: stage === 'welcome' && showWelcome ? 'auto' : 'none',
          willChange: 'opacity, transform',
        }}
      >
        <div
          className="text-white font-bold"
          style={{
            fontSize: '4rem',
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", sans-serif',
          }}
        >
          欢迎使用RuaBot框架
        </div>
        <div
          className="text-white text-2xl mt-6 font-medium"
          style={{
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", sans-serif',
          }}
        >
          Welcome to RuaBot Framework
        </div>
      </div>
    </div>
  )
}

