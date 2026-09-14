import { describe, expect, it } from "vitest";
import { float32ToPCM16, rms } from "./audio";

describe("float32ToPCM16", () => {
  it("converts silence to zeros", () => {
    const input = new Float32Array([0, 0, 0]);
    const output = new Int16Array(float32ToPCM16(input));
    expect(Array.from(output)).toEqual([0, 0, 0]);
  });

  it("converts full-scale positive and negative samples correctly", () => {
    const input = new Float32Array([1, -1]);
    const output = new Int16Array(float32ToPCM16(input));
    expect(output[0]).toBe(0x7fff);
    expect(output[1]).toBe(-0x8000);
  });

  it("clips out-of-range values instead of overflowing", () => {
    const input = new Float32Array([2.5, -3.0]);
    const output = new Int16Array(float32ToPCM16(input));
    expect(output[0]).toBe(0x7fff);
    expect(output[1]).toBe(-0x8000);
  });

  it("preserves sample count", () => {
    const input = new Float32Array(4096);
    const output = new Int16Array(float32ToPCM16(input));
    expect(output.length).toBe(4096);
  });

  it("scales a mid-range value proportionally", () => {
    const input = new Float32Array([0.5]);
    const output = new Int16Array(float32ToPCM16(input));
    expect(output[0]).toBeCloseTo(0.5 * 0x7fff, -1);
  });
});

describe("rms", () => {
  it("is zero for silence", () => {
    expect(rms(new Float32Array([0, 0, 0, 0]))).toBe(0);
  });

  it("is 1 for a full-scale constant signal", () => {
    expect(rms(new Float32Array([1, 1, 1, 1]))).toBeCloseTo(1);
  });

  it("is nonzero and less than peak for a varying signal", () => {
    const level = rms(new Float32Array([1, -1, 1, -1]));
    expect(level).toBeCloseTo(1);
    expect(level).toBeGreaterThan(0);
  });

  it("is proportional to amplitude", () => {
    const quiet = rms(new Float32Array([0.1, -0.1, 0.1, -0.1]));
    const loud = rms(new Float32Array([0.5, -0.5, 0.5, -0.5]));
    expect(loud).toBeGreaterThan(quiet);
  });
});
