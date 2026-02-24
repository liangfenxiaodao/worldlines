import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import DigestList from "./pages/DigestList";
import DigestDetail from "./pages/DigestDetail";
import ItemList from "./pages/ItemList";
import ItemDetail from "./pages/ItemDetail";
import ExposureList from "./pages/ExposureList";
import TickerIndex from "./pages/TickerIndex";
import TickerDetail from "./pages/TickerDetail";
import SummaryList from "./pages/SummaryList";
import Runs from "./pages/Runs";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="summaries" element={<SummaryList />} />
        <Route path="digests" element={<DigestList />} />
        <Route path="digests/:date" element={<DigestDetail />} />
        <Route path="items" element={<ItemList />} />
        <Route path="items/:id" element={<ItemDetail />} />
        <Route path="exposures" element={<ExposureList />} />
        <Route path="exposures/tickers" element={<TickerIndex />} />
        <Route path="exposures/:ticker" element={<TickerDetail />} />
        <Route path="runs" element={<Runs />} />
      </Route>
    </Routes>
  );
}
