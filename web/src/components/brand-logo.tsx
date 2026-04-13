interface BrandLogoProps {
  size?: number;
}

export function BrandLogo({ size = 44 }: BrandLogoProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 80 80" fill="none">
      <polygon points="40,8 67.7,24 67.7,56 40,72 12.3,56 12.3,24" stroke="#2DD4BF" strokeWidth="0.6" opacity="0.14" fill="none"/>
      <line x1="40" y1="40" x2="40" y2="8" stroke="#2DD4BF" strokeWidth="1.2" opacity="0.5"/>
      <line x1="40" y1="40" x2="67.7" y2="24" stroke="#2DD4BF" strokeWidth="1.2" opacity="0.5"/>
      <line x1="40" y1="40" x2="67.7" y2="56" stroke="#2DD4BF" strokeWidth="1.2" opacity="0.5"/>
      <line x1="40" y1="40" x2="40" y2="72" stroke="#2DD4BF" strokeWidth="1.2" opacity="0.5"/>
      <line x1="40" y1="40" x2="12.3" y2="56" stroke="#2DD4BF" strokeWidth="1.2" opacity="0.5"/>
      <line x1="40" y1="40" x2="12.3" y2="24" stroke="#2DD4BF" strokeWidth="1.2" opacity="0.5"/>
      <circle cx="40" cy="8" r="3.2" fill="#2DD4BF"/>
      <circle cx="67.7" cy="24" r="3.2" fill="#2DD4BF" opacity="0.72"/>
      <circle cx="67.7" cy="56" r="3.2" fill="#2DD4BF" opacity="0.72"/>
      <circle cx="40" cy="72" r="3.2" fill="#2DD4BF"/>
      <circle cx="12.3" cy="56" r="3.2" fill="#2DD4BF" opacity="0.72"/>
      <circle cx="12.3" cy="24" r="3.2" fill="#2DD4BF" opacity="0.72"/>
      <circle cx="40" cy="40" r="7" fill="#2DD4BF"/>
      <circle cx="40" cy="40" r="3" fill="#060F1E"/>
    </svg>
  );
}
