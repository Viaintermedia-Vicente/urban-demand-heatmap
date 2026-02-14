import "./App.css";

function App() {
  return (
    <div className="app">
      <header className="app__header">
        <h1>Hotspots urbanos – demo TFM</h1>
        <p>Selecciona fecha, hora y categorías (próximamente).</p>
      </header>
      <main>
        <div className="map-placeholder">
          <span>Aquí irá el mapa</span>
        </div>
      </main>
    </div>
  );
}

export default App;
