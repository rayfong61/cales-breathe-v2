import {
    Routes,
    Route,
  } from "react-router-dom";

  import Navbar from "./components/Navbar";
  import Footer from "./components/Footer";
  import Home from "./pages/Home";
  import Services from "./pages/Services";
  import Booking from "./pages/Booking";
  import BookingDateTimeContent from "./pages/Booking-step2";
  import BookingClientContent from "./pages/Booking-step3";
  import Login from "./pages/Login";
  import Account from "./pages/Account";
  import ScrollToTop from "./components/ScrollToTop";
  
  
  function App() {
    
    return (
      <>
        <ScrollToTop />
        <Navbar />
        <div className="min-h-screen">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/services" element={<Services />} />
            <Route path="/booking" element={<Booking />} />
            <Route path="/booking-step2" element={<BookingDateTimeContent />} />
            <Route path="/booking-step3" element={<BookingClientContent />} />
            <Route path="/login" element={<Login />} />
            <Route path="/account" element={<Account />} />
          </Routes>
        </div>
        <Footer />
      </>
    );
  }
  
  export default App;
