import { Route, Routes, useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "motion/react";
import Navbar from "./components/Navbar";
import Footer from "./components/Footer";
import Toaster from "./components/Toaster";
import Home from "./pages/Home";
import Search from "./pages/Search";
import Product from "./pages/Product";
import Saved from "./pages/Saved";
import Account from "./pages/Account";
import NotFound from "./pages/NotFound";

// Fades pages in and out when you move around.
function Page({ children }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.28, ease: "easeOut" }}
    >
      {children}
    </motion.div>
  );
}

export default function App() {
  const location = useLocation();
  return (
    <div className="min-h-screen">
      <Navbar />
      <AnimatePresence mode="wait">
        <Routes location={location} key={location.pathname}>
          <Route path="/" element={<Page><Home /></Page>} />
          <Route path="/search" element={<Page><Search /></Page>} />
          <Route path="/product" element={<Page><Product /></Page>} />
          <Route path="/saved" element={<Page><Saved /></Page>} />
          <Route path="/account" element={<Page><Account /></Page>} />
          <Route path="*" element={<Page><NotFound /></Page>} />
        </Routes>
      </AnimatePresence>
      <Footer />
      <Toaster />
    </div>
  );
}