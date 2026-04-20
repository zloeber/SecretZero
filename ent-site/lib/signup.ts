import { z } from "zod";

export const signupSchema = z.object({
  email: z.string().email().max(320),
  company: z.string().max(200).optional().default(""),
  useCase: z.string().max(1200).optional().default(""),
});

export type SignupPayload = z.infer<typeof signupSchema>;
