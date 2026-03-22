import { Routes, Route } from "react-router-dom";
import PrivateApp from "./PrivateApp.jsx";
import PublicIntakePage from "./pages/PublicIntakePage.jsx";

export default function App() {
  return (
    <Routes>
      <Route path="/intake/:slug" element={<PublicIntakePage />} />
      <Route path="/*" element={<PrivateApp />} />
    </Routes>
  );
}
