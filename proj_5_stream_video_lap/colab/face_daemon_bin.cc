/*
 * Compile on Google Colab (uClibc RV1106 toolchain):
 *   CXX=/content/luckfox-pico/tools/linux/toolchain/arm-rockchip830-linux-uclibcgnueabihf/bin/arm-rockchip830-linux-uclibcgnueabihf-g++
 *   $CXX -O3 -mfpu=neon -mfloat-abi=hard -std=c++11 face_daemon_bin.cc -I/content/rknn_model_zoo/3rdparty/rknpu2/include -I/content/rknn_model_zoo/3rdparty/stb_image -L/content/rknn_model_zoo/3rdparty/rknpu2/Linux/armhf-uclibc -lrknnmrt -lpthread -lm -o rknn_face_daemon
 */
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#define STBI_ONLY_JPEG
#define STB_IMAGE_IMPLEMENTATION
#include "rknn_api.h"
#include "stb_image.h"

struct FaceBox {
  float x1, y1, x2, y2;
  float score;
  float lm[10];
  std::vector<float> emb;
};

struct RknnZeroCopy {
  rknn_context ctx = 0;
  rknn_input_output_num io_num{};
  rknn_tensor_attr in_attr{};
  rknn_tensor_mem* in_mem = nullptr;
  std::vector<rknn_tensor_attr> out_attrs;
  std::vector<rknn_tensor_mem*> out_mems;
  int model_w = 0, model_h = 0, in_stride = 0;

  bool init(const char* path) {
    FILE* fp = fopen(path, "rb");
    if (!fp) {
      fprintf(stderr, "Cannot open %s\n", path);
      return false;
    }
    fseek(fp, 0, SEEK_END);
    size_t sz = ftell(fp);
    fseek(fp, 0, SEEK_SET);
    std::vector<uint8_t> buf(sz);
    if (fread(buf.data(), 1, sz, fp) != sz) {
      fclose(fp);
      return false;
    }
    fclose(fp);

    int ret = rknn_init(&ctx, buf.data(), sz, 0, nullptr);
    if (ret < 0) {
      fprintf(stderr, "rknn_init %s fail %d\n", path, ret);
      return false;
    }

    rknn_query(ctx, RKNN_QUERY_IN_OUT_NUM, &io_num, sizeof(io_num));
    memset(&in_attr, 0, sizeof(in_attr));
    in_attr.index = 0;
    rknn_query(ctx, RKNN_QUERY_NATIVE_INPUT_ATTR, &in_attr, sizeof(in_attr));
    in_attr.type = RKNN_TENSOR_UINT8;
    in_attr.fmt = RKNN_TENSOR_NHWC;
    model_h = in_attr.dims[1];
    model_w = in_attr.dims[2];
    in_stride = in_attr.w_stride >= (uint32_t)model_w ? (int)in_attr.w_stride : model_w;

    in_mem = rknn_create_mem(ctx, in_attr.size_with_stride);
    if (!in_mem || rknn_set_io_mem(ctx, in_mem, &in_attr) < 0) return false;

    out_attrs.resize(io_num.n_output);
    out_mems.resize(io_num.n_output, nullptr);
    for (uint32_t i = 0; i < io_num.n_output; i++) {
      memset(&out_attrs[i], 0, sizeof(rknn_tensor_attr));
      out_attrs[i].index = i;
      rknn_query(ctx, RKNN_QUERY_NATIVE_OUTPUT_ATTR, &out_attrs[i], sizeof(rknn_tensor_attr));
      out_mems[i] = rknn_create_mem(ctx, out_attrs[i].size_with_stride);
      if (!out_mems[i] || rknn_set_io_mem(ctx, out_mems[i], &out_attrs[i]) < 0) return false;
    }
    return true;
  }

  int run() {
    rknn_mem_sync(ctx, in_mem, RKNN_MEMORY_SYNC_TO_DEVICE);
    int ret = rknn_run(ctx, nullptr);
    for (uint32_t i = 0; i < io_num.n_output; i++) {
      rknn_mem_sync(ctx, out_mems[i], RKNN_MEMORY_SYNC_FROM_DEVICE);
    }
    return ret;
  }

  void destroy() {
    if (in_mem) rknn_destroy_mem(ctx, in_mem);
    for (auto* m : out_mems) {
      if (m) rknn_destroy_mem(ctx, m);
    }
    if (ctx) rknn_destroy(ctx);
  }
};

static inline float fp16_to_fp32(uint16_t h) {
  uint32_t sign = (uint32_t)(h & 0x8000) << 16;
  uint32_t exp = (h & 0x7C00) >> 10;
  uint32_t mant = (h & 0x03FF);
  uint32_t f;
  if (exp == 0) {
    if (mant == 0) {
      f = sign;
    } else {
      exp = 1;
      while ((mant & 0x0400) == 0) {
        mant <<= 1;
        exp--;
      }
      mant &= 0x03FF;
      f = sign | ((exp + 112) << 23) | (mant << 13);
    }
  } else if (exp == 31) {
    f = sign | 0x7F800000 | (mant << 13);
  } else {
    f = sign | ((exp + 112) << 23) | (mant << 13);
  }
  float res;
  memcpy(&res, &f, sizeof(res));
  return res;
}

static inline float get_val(const void* data, int idx, const rknn_tensor_attr& attr) {
  if (attr.type == RKNN_TENSOR_INT8)
    return ((float)((const int8_t*)data)[idx] - (float)attr.zp) * attr.scale;
  if (attr.type == RKNN_TENSOR_UINT8)
    return ((float)((const uint8_t*)data)[idx] - (float)attr.zp) * attr.scale;
  if (attr.type == RKNN_TENSOR_FLOAT16)
    return fp16_to_fp32(((const uint16_t*)data)[idx]);
  return ((const float*)data)[idx];
}

static float iou(const FaceBox& a, const FaceBox& b) {
  float xx1 = std::max(a.x1, b.x1), yy1 = std::max(a.y1, b.y1);
  float xx2 = std::min(a.x2, b.x2), yy2 = std::min(a.y2, b.y2);
  float inter = std::max(0.0f, xx2 - xx1) * std::max(0.0f, yy2 - yy1);
  float area_a = std::max(0.0f, a.x2 - a.x1) * std::max(0.0f, a.y2 - a.y1);
  float area_b = std::max(0.0f, b.x2 - b.x1) * std::max(0.0f, b.y2 - b.y1);
  return inter / (area_a + area_b - inter + 1e-6f);
}

struct Prior {
  float cx, cy, sx, sy;
};

static std::vector<Prior> generate_priors(int img_w, int img_h) {
  std::vector<Prior> priors;
  const int steps[3] = {8, 16, 32};
  const int min_sizes[3][2] = {{16, 32}, {64, 128}, {256, 512}};
  for (int k = 0; k < 3; k++) {
    int fw = (int)ceil((float)img_w / steps[k]);
    int fh = (int)ceil((float)img_h / steps[k]);
    for (int i = 0; i < fh; i++) {
      for (int j = 0; j < fw; j++) {
        for (int m = 0; m < 2; m++) {
          priors.push_back({(j + 0.5f) * steps[k] / img_w,
                            (i + 0.5f) * steps[k] / img_h,
                            (float)min_sizes[k][m] / img_w,
                            (float)min_sizes[k][m] / img_h});
        }
      }
    }
  }
  return priors;
}

static void letterbox_rgb(const uint8_t* src, int sw, int sh,
                          uint8_t* dst, int dw, int dh, int dst_stride,
                          float& scale, int& pad_x, int& pad_y) {
  scale = std::min((float)dw / sw, (float)dh / sh);
  int nw = (int)(sw * scale), nh = (int)(sh * scale);
  pad_x = (dw - nw) / 2;
  pad_y = (dh - nh) / 2;
  memset(dst, 0, (size_t)dst_stride * dh * 3);

  if (nw == sw && nh == sh) {
    size_t row_bytes = (size_t)sw * 3;
    for (int y = 0; y < sh; y++) {
      memcpy(dst + ((y + pad_y) * dst_stride + pad_x) * 3, src + y * row_bytes, row_bytes);
    }
    return;
  }

  for (int y = 0; y < nh; y++) {
    int sy = std::min(sh - 1, (int)(y / scale));
    uint8_t* drow = dst + ((y + pad_y) * dst_stride + pad_x) * 3;
    const uint8_t* srow = src + sy * sw * 3;
    for (int x = 0; x < nw; x++) {
      int sx = std::min(sw - 1, (int)(x / scale));
      drow[x * 3 + 0] = srow[sx * 3 + 0];
      drow[x * 3 + 1] = srow[sx * 3 + 1];
      drow[x * 3 + 2] = srow[sx * 3 + 2];
    }
  }
}

static void align_face_112(const uint8_t* src, int sw, int sh,
                           const float lm[10], uint8_t* dst, int dw, int dh, int dst_stride) {
  static const float ref[5][2] = {
      {38.2946f, 51.6963f}, {73.5318f, 51.5014f},
      {56.0252f, 71.7366f}, {41.5493f, 92.3655f}, {70.7299f, 92.2041f}};
  float scale_x = (float)dw / 112.0f, scale_y = (float)dh / 112.0f;
  float mxd = 0, myd = 0, mxs = 0, mys = 0;
  for (int i = 0; i < 5; i++) {
    mxd += ref[i][0] * scale_x;
    myd += ref[i][1] * scale_y;
    mxs += lm[i * 2];
    mys += lm[i * 2 + 1];
  }
  mxd /= 5.0f;
  myd /= 5.0f;
  mxs /= 5.0f;
  mys /= 5.0f;

  float num_a = 0, num_b = 0, denom = 0;
  for (int i = 0; i < 5; i++) {
    float dx = ref[i][0] * scale_x - mxd;
    float dy = ref[i][1] * scale_y - myd;
    float sx = lm[i * 2] - mxs;
    float sy = lm[i * 2 + 1] - mys;
    num_a += dx * sx + dy * sy;
    num_b += dx * sy - dy * sx;
    denom += dx * dx + dy * dy;
  }
  float a = num_a / (denom + 1e-6f);
  float b = num_b / (denom + 1e-6f);
  float tx = mxs - (a * mxd - b * myd);
  float ty = mys - (b * mxd + a * myd);

  for (int y = 0; y < dh; y++) {
    uint8_t* out_row = dst + y * dst_stride * 3;
    for (int x = 0; x < dw; x++) {
      float sx = a * x - b * y + tx;
      float sy = b * x + a * y + ty;
      uint8_t* out = out_row + x * 3;
      int x0 = (int)floorf(sx), y0 = (int)floorf(sy);
      if (x0 < 0 || y0 < 0 || x0 + 1 >= sw || y0 + 1 >= sh) {
        out[0] = out[1] = out[2] = 0;
        continue;
      }
      float fx = sx - x0, fy = sy - y0;
      const uint8_t* p00 = src + (y0 * sw + x0) * 3;
      const uint8_t* p10 = p00 + 3;
      const uint8_t* p01 = p00 + sw * 3;
      const uint8_t* p11 = p01 + 3;
      for (int c = 0; c < 3; c++) {
        float v = (1 - fx) * (1 - fy) * p00[c] + fx * (1 - fy) * p10[c] +
                  (1 - fx) * fy * p01[c] + fx * fy * p11[c];
        out[c] = (uint8_t)std::min(255.0f, std::max(0.0f, v));
      }
    }
  }
}

static bool read_exact(FILE* fp, void* dst, size_t n) {
  uint8_t* p = (uint8_t*)dst;
  size_t got = 0;
  while (got < n) {
    size_t r = fread(p + got, 1, n - got, fp);
    if (r == 0) return false;
    got += r;
  }
  return true;
}

int main(int argc, char** argv) {
  if (argc < 3) {
    fprintf(stderr, "Usage: %s <RetinaFace.rknn> <MobileFaceNet.rknn> [--bin]\n", argv[0]);
    return 1;
  }
  bool bin_mode = (argc >= 4 && strcmp(argv[3], "--bin") == 0);

  RknnZeroCopy det, rec;
  if (!det.init(argv[1]) || !rec.init(argv[2])) return 1;

  auto priors = generate_priors(det.model_w, det.model_h);
  int emb_dim = rec.out_attrs[0].n_elems;

  printf("%s\n", bin_mode ? "READY_BIN" : "READY");
  fflush(stdout);

  std::vector<uint8_t> jpg_buf;
  char line[512];

  while (true) {
    int sw = 0, sh = 0, sc = 0;
    uint8_t* img = nullptr;

    auto td0 = std::chrono::steady_clock::now();
    if (bin_mode) {
      uint8_t hdr[4];
      if (!read_exact(stdin, hdr, 4)) break;
      uint32_t sz = ((uint32_t)hdr[0] << 24) | ((uint32_t)hdr[1] << 16) |
                    ((uint32_t)hdr[2] << 8) | (uint32_t)hdr[3];
      if (sz == 0 || sz > 8u * 1024u * 1024u) {
        printf("{\"err\":\"bad frame size\",\"faces\":[]}\n");
        fflush(stdout);
        break;
      }
      if (jpg_buf.size() < sz) jpg_buf.resize(sz);
      if (!read_exact(stdin, jpg_buf.data(), sz)) break;
      img = stbi_load_from_memory(jpg_buf.data(), (int)sz, &sw, &sh, &sc, 3);
    } else {
      if (!fgets(line, sizeof(line), stdin)) break;
      size_t len = strlen(line);
      while (len > 0 && (line[len - 1] == '\n' || line[len - 1] == '\r')) line[--len] = '\0';
      if (len == 0) continue;
      img = stbi_load(line, &sw, &sh, &sc, 3);
    }
    auto td1 = std::chrono::steady_clock::now();
    double dec_ms = std::chrono::duration<double, std::milli>(td1 - td0).count();

    if (!img) {
      printf("{\"err\":\"stbi_load fail\",\"dec_ms\":%.2f,\"faces\":[]}\n", dec_ms);
      fflush(stdout);
      continue;
    }

    float scale = 1.0f;
    int pad_x = 0, pad_y = 0;
    letterbox_rgb(img, sw, sh, (uint8_t*)det.in_mem->virt_addr,
                  det.model_w, det.model_h, det.in_stride, scale, pad_x, pad_y);

    auto t0 = std::chrono::steady_clock::now();
    int ret = det.run();
    auto t1 = std::chrono::steady_clock::now();
    double det_ms = std::chrono::duration<double, std::milli>(t1 - t0).count();

    std::vector<FaceBox> cand;
    if (ret >= 0) {
      for (int i = 0; i < (int)priors.size(); i++) {
        float score = get_val(det.out_mems[1]->virt_addr, i * 2 + 1, det.out_attrs[1]);
        if (score < 0.5f) continue;

        float l0 = get_val(det.out_mems[0]->virt_addr, i * 4 + 0, det.out_attrs[0]);
        float l1 = get_val(det.out_mems[0]->virt_addr, i * 4 + 1, det.out_attrs[0]);
        float l2 = get_val(det.out_mems[0]->virt_addr, i * 4 + 2, det.out_attrs[0]);
        float l3 = get_val(det.out_mems[0]->virt_addr, i * 4 + 3, det.out_attrs[0]);
        const Prior& p = priors[i];
        float cx = p.cx + l0 * 0.1f * p.sx, cy = p.cy + l1 * 0.1f * p.sy;
        float bw = p.sx * expf(l2 * 0.2f), bh = p.sy * expf(l3 * 0.2f);

        FaceBox fb;
        fb.x1 = ((cx - bw * 0.5f) * det.model_w - pad_x) / scale;
        fb.y1 = ((cy - bh * 0.5f) * det.model_h - pad_y) / scale;
        fb.x2 = ((cx + bw * 0.5f) * det.model_w - pad_x) / scale;
        fb.y2 = ((cy + bh * 0.5f) * det.model_h - pad_y) / scale;
        fb.score = score;
        for (int k = 0; k < 5; k++) {
          float lx = get_val(det.out_mems[2]->virt_addr, i * 10 + k * 2 + 0, det.out_attrs[2]);
          float ly = get_val(det.out_mems[2]->virt_addr, i * 10 + k * 2 + 1, det.out_attrs[2]);
          fb.lm[k * 2 + 0] = ((p.cx + lx * 0.1f * p.sx) * det.model_w - pad_x) / scale;
          fb.lm[k * 2 + 1] = ((p.cy + ly * 0.1f * p.sy) * det.model_h - pad_y) / scale;
        }
        cand.push_back(fb);
      }
    }

    std::sort(cand.begin(), cand.end(),
              [](const FaceBox& a, const FaceBox& b) { return a.score > b.score; });
    std::vector<FaceBox> kept;
    for (const auto& c : cand) {
      bool sup = false;
      for (const auto& k : kept) {
        if (iou(c, k) > 0.4f) {
          sup = true;
          break;
        }
      }
      if (!sup) kept.push_back(c);
      if (kept.size() >= 3) break;
    }

    double rec_ms = 0.0;
    for (auto& f : kept) {
      align_face_112(img, sw, sh, f.lm, (uint8_t*)rec.in_mem->virt_addr,
                     rec.model_w, rec.model_h, rec.in_stride);
      auto tr0 = std::chrono::steady_clock::now();
      int rret = rec.run();
      auto tr1 = std::chrono::steady_clock::now();
      rec_ms += std::chrono::duration<double, std::milli>(tr1 - tr0).count();

      if (rret >= 0) {
        f.emb.resize(emb_dim);
        float norm = 0.0f;
        for (int d = 0; d < emb_dim; d++) {
          float v = get_val(rec.out_mems[0]->virt_addr, d, rec.out_attrs[0]);
          f.emb[d] = v;
          norm += v * v;
        }
        norm = sqrtf(norm) + 1e-6f;
        for (int d = 0; d < emb_dim; d++) f.emb[d] /= norm;
      }
    }
    stbi_image_free(img);

    printf("{\"npu_ms\":%.2f,\"det_ms\":%.2f,\"rec_ms\":%.2f,\"dec_ms\":%.2f,\"w\":%d,\"h\":%d,\"faces\":[",
           det_ms + rec_ms, det_ms, rec_ms, dec_ms, sw, sh);
    for (size_t i = 0; i < kept.size(); i++) {
      const auto& f = kept[i];
      if (i > 0) printf(",");
      printf("{\"score\":%.3f,\"box\":[%.1f,%.1f,%.1f,%.1f],\"lm\":[%.1f,%.1f,%.1f,%.1f,%.1f,%.1f,%.1f,%.1f,%.1f,%.1f],\"emb\":[",
             f.score, f.x1, f.y1, f.x2, f.y2,
             f.lm[0], f.lm[1], f.lm[2], f.lm[3], f.lm[4],
             f.lm[5], f.lm[6], f.lm[7], f.lm[8], f.lm[9]);
      for (size_t d = 0; d < f.emb.size(); d++) {
        if (d > 0) printf(",");
        printf("%.4f", f.emb[d]);
      }
      printf("]}");
    }
    printf("]}\n");
    fflush(stdout);
  }

  det.destroy();
  rec.destroy();
  return 0;
}
