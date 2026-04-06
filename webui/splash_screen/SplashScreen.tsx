import { useState, useEffect } from 'react'
import { api } from '../src/utils/api'
import { Sparkles } from 'lucide-react'

interface SplashScreenProps {
  onComplete: () => void
}

export default function SplashScreen({ onComplete }: SplashScreenProps) {
  const [stage, setStage] = useState<'init' | 'intro' | 'brand' | 'transition' | 'complete'>('init')

  useEffect(() => {
    const sequence = async () => {
      try {
        await new Promise(resolve => setTimeout(resolve, 800)) 
        
        setStage('intro')
        await new Promise(resolve => setTimeout(resolve, 3000)) // 
        
        //  intro duration-1000 = 1
        await new Promise(resolve => setTimeout(resolve, 1200)) 
        
        setStage('brand')
      } catch (error) {
        console.error('Splash sequence error:', error)
      }
    }

    sequence()

    const timer = setTimeout(() => {
      onComplete()
    }, 60000)

    return () => clearTimeout(timer)
  }, [onComplete])

  const handleEnter = async () => {
    setStage('transition')
    await new Promise(resolve => setTimeout(resolve, 500))
    setStage('complete')
    api.markSplashScreenShown().catch(() => {})
    await new Promise(resolve => setTimeout(resolve, 100))
    onComplete()
  }

  return (
    <div className={`fixed inset-0 z-[9999] flex items-center justify-center overflow-hidden transition-colors duration-1000 ${
      stage === 'transition' || stage === 'complete' ? 'bg-white' : 'bg-[#050505]'
    }`}>
      {/*  */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[-20%] left-[-10%] w-[70%] h-[70%] bg-blue-600/20 blur-[150px] rounded-full animate-aurora-1" />
        <div className="absolute bottom-[-20%] right-[-10%] w-[80%] h-[80%] bg-purple-600/20 blur-[180px] rounded-full animate-aurora-2" />
        <div className="absolute top-[20%] right-[10%] w-[50%] h-[50%] bg-indigo-600/15 blur-[120px] rounded-full animate-aurora-3" />
      </div>

      {/*  */}
      <div className="absolute inset-0 opacity-[0.05] pointer-events-none mix-blend-overlay bg-[url('https://grainy-gradients.vercel.app/noise.svg')]" />

      <div className="relative z-10 w-full h-full flex items-center justify-center">
        
        {/* Intro Stage: "" */}
        <div className={`absolute transition-all duration-1000 ease-in-out flex flex-col items-center ${
          stage === 'intro' ? 'opacity-100 translate-y-0 scale-100 rotate-0' : 'opacity-0 translate-y-12 scale-90 rotate-2 pointer-events-none'
        }`}>
          <div className="text-6xl md:text-[10rem] font-black bg-clip-text text-transparent bg-gradient-to-b from-white via-white to-white/20 mb-6 tracking-tighter leading-none">
            
          </div>
          <div className="text-xl md:text-2xl text-blue-400 font-light tracking-[0.5em] uppercase opacity-60 text-center px-4">
            Welcome back to your dashboard
          </div>
        </div>

        {/* Brand Stage: "RuaBot" */}
        <div className={`absolute transition-all duration-1200 cubic-bezier(0.23, 1, 0.32, 1) flex flex-col items-center ${
          stage === 'brand' ? 'opacity-100 translate-y-0 scale-100' : 'opacity-0 translate-y-20 scale-90 pointer-events-none'
        }`}>
          <div className="relative mb-12">
            <div className="absolute inset-0 bg-blue-500 blur-[80px] opacity-40 animate-pulse" />
            <div className="p-8 bg-gradient-to-br from-blue-500/20 to-purple-500/20 backdrop-blur-3xl rounded-[2.5rem] border border-white/20 relative z-10 group overflow-hidden">
              <Sparkles className="w-24 h-24 text-blue-400 animate-bounce-subtle" />
            </div>
          </div>
          
          <div className="text-5xl md:text-[6rem] font-[1000] tracking-tighter mb-8 text-center leading-[0.9] px-4">
            <span className="bg-clip-text text-transparent bg-gradient-to-r from-blue-400 via-white to-purple-500 animate-gradient-x drop-shadow-[0_0_30px_rgba(59,130,246,0.5)]">
              RuaBot Framework
            </span>
          </div>
          <div className="h-px w-48 bg-gradient-to-r from-transparent via-blue-500/50 to-transparent mb-10" />
          <div className="text-xl md:text-2xl text-gray-400 font-extralight tracking-[0.4em] text-center px-4 uppercase opacity-80 mb-12">
            Building the <span className="text-white font-normal">Next-Gen</span> Intelligence
          </div>
          
          {/*  */}
          <button
            onClick={handleEnter}
            className="px-12 py-4 bg-gradient-to-r from-blue-500 to-purple-500 text-white font-semibold text-lg rounded-full shadow-lg hover:shadow-xl hover:scale-105 transition-all duration-300 backdrop-blur-sm border border-white/20"
          >
            
          </button>
        </div>
      </div>

      {/*  */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-blue-500/10 to-transparent h-[2px] w-full animate-scan" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(59,130,246,0.05)_0%,rgba(0,0,0,0)_70%)]" />
      </div>

      <style dangerouslySetInnerHTML={{ __html: `
        @keyframes aurora-1 {
          0%, 100% { transform: translate(0, 0) scale(1) rotate(0deg); }
          33% { transform: translate(15%, 15%) scale(1.2) rotate(5deg); }
          66% { transform: translate(-10%, 20%) scale(0.9) rotate(-5deg); }
        }
        @keyframes aurora-2 {
          0%, 100% { transform: translate(0, 0) scale(1.3) rotate(0deg); }
          33% { transform: translate(-15%, -10%) scale(1.1) rotate(-10deg); }
          66% { transform: translate(10%, -20%) scale(1.4) rotate(10deg); }
        }
        @keyframes aurora-3 {
          0%, 100% { transform: translate(0, 0) opacity: 0.15; }
          50% { transform: translate(20%, -15%) opacity: 0.4; }
        }
        @keyframes scan {
          0% { transform: translateY(-100vh); opacity: 0; }
          50% { opacity: 1; }
          100% { transform: translateY(100vh); opacity: 0; }
        }
        @keyframes bounce-subtle {
          0%, 100% { transform: translateY(0) scale(1); filter: drop-shadow(0 0 20px rgba(59,130,246,0.3)); }
          50% { transform: translateY(-15px) scale(1.05); filter: drop-shadow(0 0 40px rgba(59,130,246,0.6)); }
        }
        @keyframes gradient-x {
          0%, 100% { background-size: 200% 200%; background-position: left center; }
          50% { background-size: 200% 200%; background-position: right center; }
        }
        
        .animate-aurora-1 { animation: aurora-1 25s infinite ease-in-out; }
        .animate-aurora-2 { animation: aurora-2 30s infinite ease-in-out; }
        .animate-aurora-3 { animation: aurora-3 22s infinite ease-in-out; }
        .animate-scan { animation: scan 10s linear infinite; }
        .animate-bounce-subtle { animation: bounce-subtle 4s infinite ease-in-out; }
        .animate-gradient-x { animation: gradient-x 8s ease infinite; }
      `}} />
    </div>
  )
}
