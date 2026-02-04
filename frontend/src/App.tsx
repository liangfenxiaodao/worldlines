import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import DigestList from "./pages/DigestList";
import DigestDetail from "./pages/DigestDetail";
import ItemList from "./pages/ItemList";
import ItemDetail from "./pages/ItemDetail";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="digests" element={<DigestList />} />
        <Route path="digests/:date" element={<DigestDetail />} />
        <Route path="items" element={<ItemList />} />
        <Route path="items/:id" element={<ItemDetail />} />
      </Route>
    </Routes>
  );
}
