import{j as e,a as c}from"./index-CtBPtBV_.js";import{r as i}from"./react-vendor-BklMCQnW.js";import{ap as m}from"./ui-vendor-f5QZhn8p.js";function b({onComplete:n}){const[a,r]=i.useState("init");i.useEffect(()=>{(async()=>{try{await new Promise(t=>setTimeout(t,800)),r("intro"),await new Promise(t=>setTimeout(t,3e3)),await new Promise(t=>setTimeout(t,1200)),r("brand")}catch(t){console.error("Splash sequence error:",t)}})();const l=setTimeout(()=>{n()},6e4);return()=>clearTimeout(l)},[n]);const o=async()=>{r("transition"),await new Promise(s=>setTimeout(s,500)),r("complete"),c.markSplashScreenShown().catch(()=>{}),await new Promise(s=>setTimeout(s,100)),n()};return e.jsxs("div",{className:`fixed inset-0 z-[9999] flex items-center justify-center overflow-hidden transition-colors duration-1000 ${a==="transition"||a==="complete"?"bg-white":"bg-[#050505]"}`,children:[e.jsxs("div",{className:"absolute inset-0 overflow-hidden pointer-events-none",children:[e.jsx("div",{className:"absolute top-[-20%] left-[-10%] w-[70%] h-[70%] bg-blue-600/20 blur-[150px] rounded-full animate-aurora-1"}),e.jsx("div",{className:"absolute bottom-[-20%] right-[-10%] w-[80%] h-[80%] bg-purple-600/20 blur-[180px] rounded-full animate-aurora-2"}),e.jsx("div",{className:"absolute top-[20%] right-[10%] w-[50%] h-[50%] bg-indigo-600/15 blur-[120px] rounded-full animate-aurora-3"})]}),e.jsx("div",{className:"absolute inset-0 opacity-[0.05] pointer-events-none mix-blend-overlay bg-[url('https://grainy-gradients.vercel.app/noise.svg')]"}),e.jsxs("div",{className:"relative z-10 w-full h-full flex items-center justify-center",children:[e.jsxs("div",{className:`absolute transition-all duration-1000 ease-in-out flex flex-col items-center ${a==="intro"?"opacity-100 translate-y-0 scale-100 rotate-0":"opacity-0 translate-y-12 scale-90 rotate-2 pointer-events-none"}`,children:[e.jsx("div",{className:"text-6xl md:text-[10rem] font-black bg-clip-text text-transparent bg-gradient-to-b from-white via-white to-white/20 mb-6 tracking-tighter leading-none",children:"嗨，别来无恙"}),e.jsx("div",{className:"text-xl md:text-2xl text-blue-400 font-light tracking-[0.5em] uppercase opacity-60 text-center px-4",children:"Welcome back to your dashboard"})]}),e.jsxs("div",{className:`absolute transition-all duration-1200 cubic-bezier(0.23, 1, 0.32, 1) flex flex-col items-center ${a==="brand"?"opacity-100 translate-y-0 scale-100":"opacity-0 translate-y-20 scale-90 pointer-events-none"}`,children:[e.jsxs("div",{className:"relative mb-12",children:[e.jsx("div",{className:"absolute inset-0 bg-blue-500 blur-[80px] opacity-40 animate-pulse"}),e.jsx("div",{className:"p-8 bg-gradient-to-br from-blue-500/20 to-purple-500/20 backdrop-blur-3xl rounded-[2.5rem] border border-white/20 relative z-10 group overflow-hidden",children:e.jsx(m,{className:"w-24 h-24 text-blue-400 animate-bounce-subtle"})})]}),e.jsx("div",{className:"text-5xl md:text-[6rem] font-[1000] tracking-tighter mb-8 text-center leading-[0.9] px-4",children:e.jsx("span",{className:"bg-clip-text text-transparent bg-gradient-to-r from-blue-400 via-white to-purple-500 animate-gradient-x drop-shadow-[0_0_30px_rgba(59,130,246,0.5)]",children:"RuaBot Framework"})}),e.jsx("div",{className:"h-px w-48 bg-gradient-to-r from-transparent via-blue-500/50 to-transparent mb-10"}),e.jsxs("div",{className:"text-xl md:text-2xl text-gray-400 font-extralight tracking-[0.4em] text-center px-4 uppercase opacity-80 mb-12",children:["Building the ",e.jsx("span",{className:"text-white font-normal",children:"Next-Gen"})," Intelligence"]}),e.jsx("button",{onClick:o,className:"px-12 py-4 bg-gradient-to-r from-blue-500 to-purple-500 text-white font-semibold text-lg rounded-full shadow-lg hover:shadow-xl hover:scale-105 transition-all duration-300 backdrop-blur-sm border border-white/20",children:"进入系统"})]})]}),e.jsxs("div",{className:"absolute inset-0 pointer-events-none",children:[e.jsx("div",{className:"absolute inset-0 bg-gradient-to-b from-transparent via-blue-500/10 to-transparent h-[2px] w-full animate-scan"}),e.jsx("div",{className:"absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(59,130,246,0.05)_0%,rgba(0,0,0,0)_70%)]"})]}),e.jsx("style",{dangerouslySetInnerHTML:{__html:`
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
      `}})]})}export{b as default};
