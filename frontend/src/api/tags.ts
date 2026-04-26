/** 标签相关 API */
import client, { API_PREFIX } from './client';
import type { Tag } from '@/types';

export const getTags = () =>
  client.get<{ tags: Tag[] }>(`${API_PREFIX}/tags`);

export const createTag = (name: string) =>
  client.post<{ id: number; message: string }>(`${API_PREFIX}/tags`, { name });

export const updateTag = (id: number, name: string) =>
  client.put<{ message: string }>(`${API_PREFIX}/tags/${id}`, { name });

export const deleteTag = (id: number) =>
  client.delete<{ message: string }>(`${API_PREFIX}/tags/${id}`);
