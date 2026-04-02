import { motion } from "framer-motion";

function Loading() {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.5 }}
      className="fixed inset-0 bg-white bg-opacity-80 flex items-center justify-center z-50"
    >
      <div className="animate-spin rounded-full h-16 w-16 border-t-4 border-red-500"></div>
    </motion.div>
  );
}

export default Loading;

