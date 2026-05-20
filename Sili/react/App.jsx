import React, { useState, useEffect, useCallback } from 'react';
import { Play, Pause, RotateCcw, Camera, ShieldAlert, Sparkles, Layout, Zap, Eye, Volume2 } from 'lucide-react';

const App = () => {
  // Estados para el control del video y la generación de imágenes
  const [isPlaying, setIsPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [currentSceneIndex, setCurrentSceneIndex] = useState(0);
  const [generatedImages, setGeneratedImages] = useState({});
  const [loading, setLoading] = useState(false);

  const duration = 40; // Segundos totales del Reel
  const apiKey = ""; // El entorno proporciona la clave automáticamente

  const scenes = [
    {
      start: 0, end: 5,
      dialogue: "¡HOLA HUMANOS! TENGO ALGO QUE DECIRLES...",
      prompt: "High-end 3D animation style, a funny villainous mosquito with black and red stripes looking directly at the camera with a sarcastic smile. Background is a vibrant tropical Ecuadorian backyard with wet grass and flower pots. Pixar-like rendering, cinematic lighting, 8k resolution.",
      detail: "Escena de apertura: El mosquito entra con confianza y rompe la cuarta pared.",
      audio: "Zumbido molesto + Música de tensión cómica"
    },
    {
      start: 5, end: 12,
      dialogue: "GRACIAS POR NO USAR CLORO EN SUS CASAS...",
      prompt: "Close-up 3D render of a mosquito character, expressive face, big eyes, detailed wings. Behind him, a blue bucket full of stagnant rainwater in a sunny tropical yard. High fidelity textures, 3D animated film style, 8k.",
      detail: "El mosquito agradece la negligencia humana con ironía.",
      audio: "Risa cínica del mosquito"
    },
    {
      start: 12, end: 20,
      dialogue: "¡MIRA ESTE CHARCO! ES EL PA-RA-ÍSO...",
      prompt: "Wide shot 3D animation of a tropical patio after rain. Puddles of water on the ground, a child's slide, and many small mosquitoes flying happily. Bright sun, high contrast, professional 3D environment.",
      detail: "Muestra los criaderos. El ambiente debe verse 'idílico' para el mosquito.",
      audio: "Ambiente de lluvia tropical + Risas de fondo"
    },
    {
      start: 20, end: 28,
      dialogue: "PERO SI USARAN CLORO LÍQUIDO... MORIRÍAMOS.",
      prompt: "Dramatic 3D scene, the mosquito looks terrified, sweating, eyes wide open in fear. White chemical mist appearing in the background. High emotional expression, cinematic 3D render, dark shadows.",
      detail: "Giro dramático. El miedo al cloro líquido como arma de desinfección.",
      audio: "Efecto de sonido dramático (Stinger)"
    },
    {
      start: 28, end: 35,
      dialogue: "¡¡¡VAMOS A MORIR!!! ¡AYUDAA!",
      prompt: "Action shot of two funny 3D mosquitoes hugging each other in panic. A bright white flash of light is about to hit them. Explosive and energetic composition, high-quality 3D rendering.",
      detail: "Clímax: La colonia de mosquitos es aniquilada por la limpieza.",
      audio: "Grito agudo + Explosión sónica"
    },
    {
      start: 35, end: 40,
      dialogue: "EL CLORO SALVA VIDAS. ÚSALO.",
      prompt: "Clean, professional final shot. Sparkling clean water surface with small bubbles. Bold, elegant typography: 'EL CLORO SALVA VIDAS'. Calming blue and white tones, high resolution, no logos.",
      detail: "Cierre institucional: Mensaje de salud pública puro y potente.",
      audio: "Música inspiradora y tranquila"
    }
  ];

  // Función de reinicio corregida
  const handleReset = useCallback(() => {
    setProgress(0);
    setCurrentSceneIndex(0);
    setIsPlaying(false);
  }, []);

  // Generación de cuadros con IA (Imagen 4.0)
  const generateCurrentFrame = async () => {
    if (loading) return;
    setLoading(true);
   
    let retryCount = 0;
    const maxRetries = 3;
   
    const attemptFetch = async () => {
      try {
        const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/imagen-4.0-generate-001:predict?key=${apiKey}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            instances: [{ prompt: scenes[currentSceneIndex].prompt }],
            parameters: { sampleCount: 1 }
          })
        });
       
        const result = await response.json();
       
        if (result.predictions && result.predictions[0]) {
          const imageUrl = `data:image/png;base64,${result.predictions[0].bytesBase64Encoded}`;
          setGeneratedImages(prev => ({ ...prev, [currentSceneIndex]: imageUrl }));
          setLoading(false);
        } else {
          throw new Error("Respuesta de API inválida");
        }
      } catch (error) {
        if (retryCount < maxRetries) {
          retryCount++;
          setTimeout(attemptFetch, 2000);
        } else {
          setLoading(false);
        }
      }
    };

    attemptFetch();
  };

  // Manejo del loop de tiempo
  useEffect(() => {
    let interval;
    if (isPlaying && progress < 100) {
      interval = setInterval(() => {
        setProgress(prev => {
          const next = prev + (100 / (duration * 10));
          return next >= 100 ? 100 : next;
        });
      }, 100);
    } else if (progress >= 100) {
      setIsPlaying(false);
    }
    return () => clearInterval(interval);
  }, [isPlaying, progress]);

  // Sincronización de escena
  useEffect(() => {
    const currentTime = (progress / 100) * duration;
    const sceneIndex = scenes.findIndex(s => currentTime >= s.start && currentTime < s.end);
    if (sceneIndex !== -1 && sceneIndex !== currentSceneIndex) {
      setCurrentSceneIndex(sceneIndex);
    }
  }, [progress, currentSceneIndex]);

  const formatTimecode = () => {
    const seconds = Math.floor((progress / 100) * duration);
    return `00:${seconds.toString().padStart(2, '0')}:00`;
  };

  return (
    <div className="min-h-screen bg-neutral-950 text-white p-4 md:p-8 font-sans selection:bg-blue-500 overflow-x-hidden">
      <header className="max-w-7xl mx-auto mb-10 flex flex-col md:flex-row justify-between items-center gap-6">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 bg-blue-600 rounded-xl flex items-center justify-center shadow-lg shadow-blue-600/20">
            <Zap className="text-white" fill="white" size={24} />
          </div>
          <div>
            <h1 className="text-2xl font-black tracking-tighter uppercase italic">Quimpac <span className="text-blue-500">Video Lab</span></h1>
            <p className="text-neutral-500 text-[10px] font-bold tracking-[0.2em] uppercase">Simulador de Campaña Pull / Render 3D</p>
          </div>
        </div>
       
        <div className="flex gap-4">
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            className="flex items-center gap-2 bg-white text-black px-8 py-3 rounded-full font-black text-sm hover:bg-blue-500 hover:text-white transition-all transform active:scale-95 shadow-xl"
          >
            {isPlaying ? <Pause size={18} /> : <Play size={18} fill="currentColor" />}
            {isPlaying ? "PAUSAR" : "REPRODUCIR REEL"}
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-10">
       
        {/* MONITOR DE VIDEO 9:16 */}
        <div className="lg:col-span-5 flex justify-center">
          <div className="relative w-full max-w-[340px] aspect-[9/16] bg-neutral-900 rounded-[3rem] border-[12px] border-neutral-800 shadow-[0_0_100px_rgba(59,130,246,0.1)] overflow-hidden">
           
            {/* Barra de progreso superior */}
            <div className="absolute top-4 left-0 right-0 px-4 z-50 flex gap-1">
              {scenes.map((_, i) => (
                <div key={i} className="h-0.5 flex-1 bg-white/20 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-white transition-all duration-100 ease-linear"
                    style={{
                      width: currentSceneIndex > i ? '100%' : (currentSceneIndex === i ? `${((progress/100*duration - scenes[i].start) / (scenes[i].end - scenes[i].start)) * 100}%` : '0%')
                    }}
                  />
                </div>
              ))}
            </div>

            {/* Visualizador de Contenido */}
            <div className="w-full h-full relative">
              {generatedImages[currentSceneIndex] ? (
                <img src={generatedImages[currentSceneIndex]} className="w-full h-full object-cover animate-in fade-in zoom-in-95 duration-700" alt="Frame 3D" />
              ) : (
                <div className="w-full h-full bg-gradient-to-b from-neutral-800 to-black flex flex-col items-center justify-center p-8 text-center">
                  {loading ? (
                    <div className="flex flex-col items-center">
                      <div className="w-10 h-10 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mb-4" />
                      <p className="text-[10px] font-black uppercase text-blue-500 tracking-widest">Renderizando Escena {currentSceneIndex + 1}...</p>
                    </div>
                  ) : (
                    <div className="flex flex-col items-center">
                      <Camera size={48} className="text-neutral-700 mb-4" />
                      <p className="text-xs text-neutral-500 font-bold mb-6 italic">Visualización 3D no generada</p>
                      <button
                        onClick={generateCurrentFrame}
                        className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-2 rounded-full text-[10px] font-black transition-all flex items-center gap-2"
                      >
                        <Sparkles size={14} /> GENERAR ARTE CONCEPTUAL
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* Subtítulos Dinámicos */}
              <div className="absolute bottom-32 left-0 right-0 px-6 text-center pointer-events-none">
                <div className="bg-yellow-400 text-black px-4 py-2 font-black text-xl uppercase italic leading-none shadow-[10px_10px_0px_0px_rgba(0,0,0,1)] transform -rotate-1 inline-block">
                  {scenes[currentSceneIndex].dialogue}
                </div>
              </div>

              {/* Timecode Overlay */}
              <div className="absolute top-8 left-6 bg-black/40 backdrop-blur-md px-3 py-1 rounded text-[10px] font-mono font-bold border border-white/10">
                {`SCN_0${currentSceneIndex + 1} // ${formatTimecode()}`}
              </div>
            </div>
          </div>
        </div>

        {/* DETALLES Y CONTROL DE DIRECCIÓN */}
        <div className="lg:col-span-7 space-y-6">
          <div className="bg-neutral-900/50 p-8 rounded-[2rem] border border-neutral-800 shadow-xl">
            <div className="flex items-center gap-2 mb-6 text-blue-400">
              <Layout size={20} />
              <h2 className="font-bold text-xs uppercase tracking-[0.2em]">Hoja de Dirección</h2>
            </div>
           
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <div className="space-y-6">
                <div>
                  <p className="text-[10px] font-black text-neutral-500 uppercase mb-2">Acción de Escena</p>
                  <p className="text-sm text-neutral-200 leading-relaxed font-medium">
                    {scenes[currentSceneIndex].detail}
                  </p>
                </div>
                <div className="flex items-center gap-3 bg-black/40 p-3 rounded-xl border border-neutral-800">
                  <Volume2 size={18} className="text-blue-500" />
                  <p className="text-[10px] font-bold text-neutral-400 uppercase tracking-wider">{scenes[currentSceneIndex].audio}</p>
                </div>
              </div>
             
              <div className="bg-black/30 p-5 rounded-2xl border border-neutral-800">
                <div className="flex items-center gap-2 mb-3 text-yellow-500">
                  <Eye size={16} />
                  <p className="text-[10px] font-black uppercase">Referencia 3D (IA Prompt)</p>
                </div>
                <p className="text-[10px] text-neutral-500 font-mono leading-relaxed italic">
                  "{scenes[currentSceneIndex].prompt}"
                </p>
              </div>
            </div>
          </div>

          {/* Timeline de Producción */}
          <div className="bg-neutral-900/50 p-6 rounded-[2rem] border border-neutral-800">
            <div className="flex justify-between items-center mb-6 px-2">
              <span className="text-[10px] font-black uppercase tracking-widest text-neutral-500">Timeline de 40 Segundos</span>
              <button onClick={handleReset} className="p-2 bg-neutral-800 hover:bg-neutral-700 rounded-full transition-colors">
                <RotateCcw size={16} />
              </button>
            </div>
            <div className="relative h-2 bg-neutral-800 rounded-full mb-6 overflow-hidden">
              <div
                className="absolute top-0 left-0 h-full bg-blue-600 shadow-[0_0_15px_rgba(37,99,235,0.5)] transition-all duration-100 ease-linear"
                style={{ width: `${progress}%` }}
              />
            </div>
            <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
              {scenes.map((s, i) => (
                <button
                  key={i}
                  onClick={() => { setProgress((s.start/duration)*100); setCurrentSceneIndex(i); }}
                  className={`px-3 py-2 rounded-xl text-[9px] font-black transition-all border ${currentSceneIndex === i ? 'bg-blue-600 border-blue-400 text-white' : 'bg-neutral-800 border-neutral-700 text-neutral-500 hover:bg-neutral-700'}`}
                >
                  ESC_0{i+1}
                </button>
              ))}
            </div>
          </div>

          <div className="bg-blue-600/10 border border-blue-500/20 p-8 rounded-[2rem] relative overflow-hidden">
            <div className="relative z-10">
              <div className="flex items-center gap-2 mb-4 text-blue-400 font-black text-xs uppercase">
                <ShieldAlert size={18} /> Nota Estratégica Quimpac
              </div>
              <p className="text-sm text-blue-100/70 leading-relaxed italic font-medium">
                "Este reel se enfoca en el miedo del villano al cloro. Al ser el único productor Chlor Alkali del país, cada vez que este video se vuelve viral y un consumidor va a comprar 'cloro' por pánico al mosquito, el beneficio fluye directamente hacia Quimpac a través de tu red de distribuidores."
              </p>
            </div>
            <div className="absolute top-0 right-0 p-8 opacity-10">
              <Zap size={120} />
            </div>
          </div>
        </div>
      </main>

      <footer className="max-w-7xl mx-auto mt-12 pt-8 border-t border-neutral-900 flex flex-col md:flex-row justify-between items-center gap-4 opacity-40">
        <p className="text-[10px] font-bold tracking-widest uppercase">Quimpac S.A. © 2024 • Laboratorio Creativo de Concientización</p>
        <div className="flex gap-2">
          <div className="w-1 h-1 rounded-full bg-blue-500" />
          <div className="w-1 h-1 rounded-full bg-white" />
          <div className="w-1 h-1 rounded-full bg-blue-500" />
        </div>
      </footer>
    </div>
  );
};

export default App;
 