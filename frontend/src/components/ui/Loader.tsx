interface LoaderProps {
  size?: "sm" | "md" | "lg";
}

const sizeMap = { sm: 16, md: 24, lg: 40 };

export default function Loader({ size = "md" }: LoaderProps) {
  const px = sizeMap[size];
  return (
    <div
      className="loader"
      style={{ width: px, height: px }}
      role="status"
      aria-label="Loading"
    />
  );
}
