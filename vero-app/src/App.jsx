import Navbar from "./components/Navbar";
import Footer from "./components/Footer";
import Toaster from "./components/Toaster";
import AnimatedBackground from "./components/AnimatedBackground";

export default function App() {
  return (
    <div className="relative min-h-screen">
      <AnimatedBackground />
      <Navbar />
      <main className="mx-auto max-w-6xl px-5 py-24">
        <h1 className="font-display text-5xl font-semibold">Vero foundation is ready.</h1>
      </main>
      <Footer />
      <Toaster />
    </div>
  );
}