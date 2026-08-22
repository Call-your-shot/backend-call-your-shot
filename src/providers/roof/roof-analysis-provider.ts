export interface RoofAnalysisInput {
  imagePath?: string | null;
  propertyId: string;
}

export interface RoofAnalysisResult {
  roofAreaM2?: number;
  usableRoofAreaM2?: number;
  confidence: "manual" | "provider_estimate";
}

export interface RoofAnalysisProvider {
  analyse(input: RoofAnalysisInput): Promise<RoofAnalysisResult>;
}

export class ManualRoofAnalysisProvider implements RoofAnalysisProvider {
  async analyse(): Promise<RoofAnalysisResult> {
    return { confidence: "manual" };
  }
}
