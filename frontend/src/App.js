import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import "./App.css";
import { AuthProvider, useAuth } from "./lib/auth";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Register from "./pages/Register";
import AppLayout from "./pages/AppLayout";
import Dashboard from "./pages/Dashboard";
import Streams from "./pages/Streams";
import Ideas from "./pages/Ideas";
import Content from "./pages/Content";
import Simulator from "./pages/Simulator";
import Coach from "./pages/Coach";
import Goals from "./pages/Goals";
import Pricing from "./pages/Pricing";
import BillingSuccess from "./pages/BillingSuccess";

function Protected({ children }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/app" element={<Protected><AppLayout /></Protected>}>
            <Route index element={<Dashboard />} />
            <Route path="streams" element={<Streams />} />
            <Route path="ideas" element={<Ideas />} />
            <Route path="content" element={<Content />} />
            <Route path="simulator" element={<Simulator />} />
            <Route path="coach" element={<Coach />} />
            <Route path="goals" element={<Goals />} />
            <Route path="pricing" element={<Pricing />} />
            <Route path="billing/success" element={<BillingSuccess />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
